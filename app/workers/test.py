from datetime import datetime
from dateutil.relativedelta import relativedelta
result = {}

now_str = datetime.strftime(datetime.now(), '%d/%m/%Y %H:%M:%S')
now = datetime.strptime(now_str, '%d/%m/%Y %H:%M:%S')

result['insurance_start_date'] = now.isoformat()
result['policy_issued_datetime'] = (now - relativedelta(days=1)).isoformat()
result['insurance_end_date'] = (now + relativedelta(years=1)).isoformat()
result.update({'is_suspecting_wrongly': True})

print(result)
