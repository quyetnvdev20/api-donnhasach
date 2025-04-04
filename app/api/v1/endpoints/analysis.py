import base64
import os

from fastapi import APIRouter, Depends, HTTPException, status, Body, Header, UploadFile, File
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from typing import List, Optional
from ....database import get_db
from ...deps import get_current_user
from ....models.image import Image
from ....schemas.image_analysis import ImageAnalysisRequest, ImageAnalysisResponse, AudioAnalysisResponse
from ....services.rabbitmq import publish_event
from ....services.firebase import FirebaseNotificationService
from ....utils.erp_db import PostgresDB
import httpx
import json
import uuid
import logging
from datetime import datetime
from app.config import ClaimImageStatus, settings
from app.utils.redis_client import redis_client


with open(f'{settings.ROOT_DIR}/app/data/list_name_dict.json', 'r', encoding='utf-8') as f:
    LIST_NAME_DICT = json.load(f)
with open(f'{settings.ROOT_DIR}/app/data/list_damage_dict.json', 'r', encoding='utf-8') as f:
    LIST_DAMAGE_DICT = json.load(f)


router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/assessment/{assessment_id}/analysis/rmqasync",
             response_model=ImageAnalysisResponse)
async def submit_image_for_analysis(
    assessment_id: str,
    request: ImageAnalysisRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Submit an image URL for analysis
    """
    # Check exist sub
    if not current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Check exist image_id and session_id
    existing_image = db.query(Image).filter(
        Image.analysis_id == str(request.analysis_id or request.image_id),
        Image.id == str(request.image_id),
        Image.assessment_id == str(assessment_id),
    ).first()
    if existing_image:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Image already exists")
    
    new_image = Image(
        analysis_id=str(request.analysis_id or request.image_id),
        assessment_id=str(assessment_id),
        image_url=request.image_url,
        id=str(request.image_id),
        device_token=request.device_token,
        keycloak_user_id=current_user.get("sub"),
        auto_analysis=request.auto_analysis,
        status=ClaimImageStatus.PENDING.value
    )
    db.add(new_image)
    db.commit()
    
    # Publish event for Image Analysis Processing Task
    await publish_event(
        exchange_name="image.analysis.direct",
        routing_key="image.uploaded",
        payload={
            "analysis_id": str(request.analysis_id or request.image_id),
            "assessment_id": str(assessment_id),
            "image_url": request.image_url,
            "keycloak_user_id": current_user.get("sub")
        }
    )
    
    return new_image

@router.get("/assessment/test")
async def test(
    db: Session = Depends(get_db)
):
    images = db.query(Image).filter(Image.analysis_id == "17406439285770").all()
    for image in images:
        
        await publish_event(
        exchange_name="image.analysis.direct",
        routing_key="image.uploaded",
        payload={
            "analysis_id": image.analysis_id,
            "assessment_id": image.assessment_id,
            "image_url": image.image_url,
            "keycloak_user_id": image.keycloak_user_id,
            "auto_analysis": image.auto_analysis
        }
    )
    return {"message": "success"}

@router.post("/assessment/{assessment_id}/analysis/upload",
             response_model=ImageAnalysisResponse)
async def process_image_analysis(
    assessment_id: str,
    request: ImageAnalysisRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Process image analysis directly without using RabbitMQ
    """
    try:
        # Check for existing image
        existing_image = db.query(Image).filter(
            Image.analysis_id == str(request.analysis_id or request.image_id),
            Image.id == str(request.image_id),
            Image.assessment_id == str(assessment_id),
        ).first()
        
        if existing_image:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Image already exists"
            )
            
        # Create new image record
        new_image = Image(
            analysis_id=str(request.analysis_id or request.image_id),
            assessment_id=str(assessment_id),
            image_url=request.image_url,
            id=str(request.image_id),
            device_token=request.device_token,
            keycloak_user_id=current_user.get("sub"),
            auto_analysis=request.auto_analysis,
            status=ClaimImageStatus.PROCESSING.value
        )
        db.add(new_image)
        db.commit()
        db.refresh(new_image)

        try:
            # Process image with GPT
            response = await process_image_with_gpt(request.image_url)
            
            if not response:
                raise ValueError("GPT analysis returned no results")

            # Update image with results
            new_image.status = ClaimImageStatus.SUCCESS.value
            new_image.list_json_data = response
            db.commit()
            db.refresh(new_image)

            # Map assessment items
            mapped_results = []
            if new_image.list_json_data:
                # Transform and map the data
                transformed_items = []
                for data_dict in new_image.list_json_data:
                    if not isinstance(data_dict, dict):
                        logger.warning(f"Invalid data format in list_json_data: {data_dict}")
                        continue
                        
                    for category, state in data_dict.items():
                        transformed_items.append({
                            "damage_name": state,
                            "item_name": category
                        })

                if transformed_items:
                    # Build query
                    placeholders = []
                    values = []
                    for i, item in enumerate(transformed_items):
                        placeholders.append(f"(iclc.name = ${2*i + 1} AND isc.name = ${2*i + 2})")
                        values.extend([item["item_name"], item["damage_name"]])

                    query = f"""
                        SELECT 
                            iclc.id AS category_id,
                            isc.id AS state_id,
                            iclc.name AS category_name,
                            isc.name AS state_name
                        FROM insurance_claim_list_category iclc
                        JOIN insurance_state_category isc ON 1=1
                        WHERE {' OR '.join(placeholders)};
                    """

                    results = await PostgresDB.execute_query(query, values)

                    if results:
                        result_map = {
                            (row["category_name"], row["state_name"]): {
                                "damage_id": row["state_id"],
                                "item_id": row["category_id"]
                            } for row in results
                        }

                        for item in transformed_items:
                            key = (item["item_name"], item["damage_name"])
                            if key in result_map:
                                item.update(result_map[key])
                                mapped_results.append(item)

            # Ensure results is valid JSON before saving
            if mapped_results:
                try:
                    results_json = json.dumps(mapped_results)
                    new_image.results = results_json
                except TypeError as e:
                    logger.error(f"Error converting mapped_results to JSON: {e}")
                    new_image.results = json.dumps([])
            else:
                new_image.results = json.dumps([])
                
            db.commit()

            # Send notification
            await send_analysis_notification(new_image, 
                                          f'tic_claim_{str(new_image.keycloak_user_id)}',
                                          "Image Analysis Complete",
                                          "Your image has been successfully analyzed.")

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            new_image.status = ClaimImageStatus.FAILED.value
            new_image.error_message = str(e)
            db.commit()

            # Send failure notification        
            await send_analysis_notification(new_image, 
                                          f'tic_claim_{str(new_image.keycloak_user_id)}',
                                          "Image Analysis Failed",
                                          "There was an error analyzing your image.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

        return new_image

    except Exception as e:
        logger.error(f"Unexpected error in process_image_analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the image"
        )


@router.post("/assessment/{assessment_id}/analysis/audio", response_model=AudioAnalysisResponse)
async def analyze_audio(
    audio_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze audio file and return detected category and status
    """
    if not audio_file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an audio file"
        )
    response = {
        "category": {
            "id": 1539,
            "name": "Cửa trước phải",
            "code": "CAR1"
        },
        "status": {
            "id": 25,
            "name": "Trầy xước",
            "code": "SCRATCH"
        }
    }

    return response

    # # Lưu file tạm thời
    # with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
    #     content = await audio_file.read()
    #     temp_file.write(content)
    #     temp_path = temp_file.name
    #
    # try:
    #     # Load model whisper
    #     model = whisper.load_model("base")
    #
    #     # Transcribe audio to text
    #     result = model.transcribe(temp_path)
    #     transcribed_text = result["text"].lower()
    #
    #     # Query để lấy danh sách category và status
    #     category_query = """
    #         SELECT id, name, code
    #         FROM insurance_claim_list_category
    #         WHERE active = true
    #     """
    #     status_query = """
    #         SELECT id, name, code
    #         FROM insurance_state_category
    #         WHERE active = true
    #     """
    #
    #     categories, statuses = await asyncio.gather(
    #         PostgresDB.execute_query(category_query),
    #         PostgresDB.execute_query(status_query)
    #     )
    #
    #     # Tìm category và status phù hợp nhất từ text
    #     matched_category = None
    #     matched_status = None
    #
    #     for category in categories:
    #         if category["name"].lower() in transcribed_text:
    #             matched_category = {
    #                 "id": category["id"],
    #                 "name": category["name"],
    #                 "code": category["code"]
    #             }
    #             break
    #
    #     for status in statuses:
    #         if status["name"].lower() in transcribed_text:
    #             matched_status = {
    #                 "id": status["id"],
    #                 "name": status["name"],
    #                 "code": status["code"]
    #             }
    #             break
    #
    #     if not matched_category or not matched_status:
    #         raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND,
    #             detail="Could not detect category or status from audio"
    #         )
    #
    #     response = {
    #         "category": {
    #             "id": 123,
    #             "name": "Cửa trước phải",
    #             "code": "abc"
    #         },
    #         "status": {
    #             "id": 456,
    #             "name": "Trầy xước",
    #             "code": "def"
    #         }
    #     }
    #
    #     return response
    #
    # except Exception as e:
    #     logger.error(f"Error analyzing audio: {str(e)}")
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail="Error analyzing audio file"
    #     )
    # finally:
    #     # Xóa file tạm
    #     if os.path.exists(temp_path):
    #         os.unlink(temp_path)



async def process_image_with_gpt(image_url: str) -> list:
    try:
        #convert image_url to base64
        async with httpx.AsyncClient() as client:
            image = await client.get(image_url)
        base64_image = base64.b64encode(image.content).decode('utf-8')

        prompt = f"""Bạn là một chuyên gia giám định xe ô tô hàng đầu thế giới. 
Hãy phân tích chính xác xem trong hình ảnh sau đây những bộ phận nào của xe ô tô bị tổn thất.
Luôn luôn lựa chọn bộ phận và tổn thất chính xác nhất từ danh sách bộ phận và danh sách tổn thất bên dưới. **Không được tự ý suy diễn hoặc tạo ra thông tin không có trong danh sách.**  

**Lưu ý quan trọng:**
**Không được nhầm lẫn giữa bên trái và bên phải của xe.**  
**Luôn xác định trái/phải dựa trên góc nhìn khi đứng từ phía sau xe.**  

**Nguyên tắc quan trọng khi xác định bộ phận trái/phải:**  
1. **Tưởng tượng bạn đang đứng phía sau xe, nhìn về phía trước.**  
2. **Bộ phận bên trái là những bộ phận nằm về phía tay trái của bạn.**  
3. **Bộ phận bên phải là những bộ phận nằm về phía tay phải của bạn.**  
4. Không xác định trái/phải theo hình ảnh mà bạn đang thấy nếu không xét đến quy tắc trên.  

**Danh sách bộ phận của xe ô tô (ID - Tên bộ phận):**  
{LIST_NAME_DICT}  

**Danh sách tổn thất có thể có của xe ô tô (ID - Tên tổn thất):**  
{LIST_DAMAGE_DICT}  

**Output yêu cầu:**  
- Trả về dữ liệu dưới dạng JSON. 
- Key là 'damage_info', value là 1 dict có key là id của bộ phận, value là id của tổn thất. ID để dạng string.
- Không trả ra bất kỳ thông tin nào khác.
"""
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        response_content = response.choices[0].message.content
        output = json.loads(response_content)["damage_info"]
        output_final = []
        
        # Process the output to handle left/right components
        for key, value in output.items():
            # Add the original component
            output_final.append({
                LIST_NAME_DICT[str(key)]: LIST_DAMAGE_DICT[str(value)]
            })
            
            # Check if this is a left component ("trái") and add the corresponding right component ("phải")
            component_name = LIST_NAME_DICT[str(key)]
            if "trái" in component_name.lower():
                # Find the corresponding right component by replacing "trái" with "phải"
                right_component_name = component_name.lower().replace("trái", "phải")
                
                # Find the ID for the right component
                right_component_id = None
                for id, name in LIST_NAME_DICT.items():
                    if name.lower() == right_component_name:
                        right_component_id = id
                        break
                
                # If found, add the right component with the same damage value
                if right_component_id:
                    output_final.append({
                        LIST_NAME_DICT[str(right_component_id)]: LIST_DAMAGE_DICT[str(value)]
                    })
            
            # Also check for right components and add corresponding left components
            elif "phải" in component_name.lower():
                # Find the corresponding left component by replacing "phải" with "trái"
                left_component_name = component_name.lower().replace("phải", "trái")
                
                # Find the ID for the left component
                left_component_id = None
                for id, name in LIST_NAME_DICT.items():
                    if name.lower() == left_component_name:
                        left_component_id = id
                        break
                
                # If found, add the left component with the same damage value
                if left_component_id:
                    output_final.append({
                        LIST_NAME_DICT[str(left_component_id)]: LIST_DAMAGE_DICT[str(value)]
                    })
                    
        return output_final

    except Exception as e:
        raise e
    
    
async def process_images_list_with_gpt(images_base64: list) -> list:
    try:
        #convert image_url to base64
        list_base64_image = []
        for image_base64 in images_base64:
            list_base64_image.append(image_base64)

        prompt = f"""Bạn là một chuyên gia giám định xe ô tô hàng đầu thế giới. 
Những hình ảnh sau đây là những hình ảnh để thể hiện một tổn thất của 1 bộ phận của xe ô tô.
Các hình ảnh sẽ được chụp từ nhiều góc độ khác nhau để bạn có thể quan sát được toàn bộ bộ phận đó.
Hãy phân tích chính xác xem những hình ảnh đó thể hiện tổn thất của bộ phận nào và tổn thất đó là tổn thất gì.

Luôn luôn lựa chọn bộ phận và tổn thất chính xác nhất từ danh sách bộ phận và danh sách tổn thất bên dưới. **Không được tự ý suy diễn hoặc tạo ra thông tin không có trong danh sách.**  
Chỉ lựa chọn 1 bộ phận và 1 tổn thất.

**Lưu ý quan trọng:**
**Không được nhầm lẫn giữa bên trái và bên phải của xe.**  
**Luôn xác định trái/phải dựa trên góc nhìn khi đứng từ phía sau xe.**  

**Nguyên tắc quan trọng khi xác định bộ phận trái/phải:**  
1. **Tưởng tượng bạn đang đứng phía sau xe, nhìn về phía trước.**  
2. **Bộ phận bên trái là những bộ phận nằm về phía tay trái của bạn.**  
3. **Bộ phận bên phải là những bộ phận nằm về phía tay phải của bạn.**  
4. Không xác định trái/phải theo hình ảnh mà bạn đang thấy nếu không xét đến quy tắc trên.  

**Danh sách bộ phận của xe ô tô (ID - Tên bộ phận):**  
{LIST_NAME_DICT}  

**Danh sách tổn thất có thể có của xe ô tô (ID - Tên tổn thất):**  
{LIST_DAMAGE_DICT}  

**Output yêu cầu:**  
- Trả về dữ liệu dưới dạng JSON. 
- Key là 'damage_info', value là 1 dict có key là id của bộ phận, value là id của tổn thất. ID để dạng string.
- Không trả ra bất kỳ thông tin nào khác.
"""
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    *[
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                        } for img_base64 in list_base64_image
                    ]
                ]
            }
        ],
        response_format={"type": "json_object"}
        )
        response_content = response.choices[0].message.content
        output = json.loads(response_content)["damage_info"]
        output_final = []
        for key, value in output.items():
            output_final.append({
                LIST_NAME_DICT[str(key)]: LIST_DAMAGE_DICT[str(value)]
            })
        return output_final

    except Exception as e:
        raise e

async def send_analysis_notification(image: Image, topic: str, title: str, body: str):
    """
    Gửi thông báo khi phân tích ảnh hoàn tất
    Args:
        image: Image object chứa thông tin ảnh đã phân tích
        mapped_results: Kết quả phân tích đã được map
    """
    
    results = image.results
    if results:
        results = json.loads(results)
    else:
        results = []
    
    notification_data = {
        "analysis_id": image.analysis_id,
        "assessment_id": image.assessment_id,
        "image_id": str(image.id),
        "image_url": str(image.image_url),
        "auto_analysis": str(image.auto_analysis),
        "results": json.dumps(results)
    }

    await FirebaseNotificationService.send_notification_to_topic(
        topic=topic,
        title=title,
        body=body,
        data=notification_data
    )