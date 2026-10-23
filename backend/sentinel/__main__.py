import logging
import os
import uvicorn
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
uvicorn.run('sentinel.app:create_app',factory=True,host='0.0.0.0',port=int(os.getenv('PORT','8000')),workers=1,proxy_headers=False)
