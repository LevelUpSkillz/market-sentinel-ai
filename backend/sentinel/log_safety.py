"""Never write OAuth callback codes into application access logs."""
import logging
class RedactAuthQuery(logging.Filter):
    def filter(self,record):
        if isinstance(record.args,tuple) and len(record.args)>=3 and isinstance(record.args[2],str) and record.args[2].startswith('/api/auth/'):
            values=list(record.args);values[2]=values[2].split('?',1)[0];record.args=tuple(values)
        return True
