import sys
import os
import time
import threading
import grpc
from concurrent import futures
import logging

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
root_path = os.path.abspath(os.path.join(FILE, '../../..'))

sys.path.append(root_path)
sys.path.append(os.path.abspath(os.path.join(root_path, '/utils/pb/fraud_detection')))
import utils.pb.database.database_pb2 as database
import utils.pb.database.database_pb2_grpc as database_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Exec-%(name)s] %(message)s")
logger = logging.getLogger(__name__)

class DatabaseService(database_grpc.DatabaseServiceServicer):
    def __init__(self):
        self.lock = threading.Lock()
        self.data = dict()
        self.is_primary = False
        self.primary_id = None
    
    def Read(self, request, context):
        return database.ReadResponse(request.key, self.data.get(request.key, -1)) # return -1 if no such item
    
    def Write(self, request, context):
        success = False
        with self.lock:
            try:
                self.data[request.key] = request.stock
                success = True
            except:
                pass
        return database.WriteResponse(success)