import secrets
import string

# Tạo chuỗi ký tự cho phép
characters = string.ascii_letters + string.digits  # a-z, A-Z, 0-9

# Tạo token 30 ký tự
token = ''.join(secrets.choice(characters) for _ in range(50))
print(token)  # Ví dụ: "8fKp2Qs9vN7xM4jL5tR3wY1hC6bD0mA"