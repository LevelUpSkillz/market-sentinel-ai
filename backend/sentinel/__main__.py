import logging
import os
import uvicorn
from copy import deepcopy
from uvicorn.config import LOGGING_CONFIG
config=deepcopy(LOGGING_CONFIG)
config['filters']={'safe_auth_queries':{'()':'sentinel.log_safety.RedactAuthQuery'}}
config['handlers']['access']['filters']=['safe_auth_queries']
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
uvicorn.run('sentinel.app:create_app',factory=True,host='0.0.0.0',port=int(os.getenv('PORT','8000')),workers=1,proxy_headers=False,log_config=config)
