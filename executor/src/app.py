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
sys.path.insert(0, os.path.join(root_path, 'utils/pb/executor'))
import utils.pb.executor.executor_pb2 as executor_pb2
import utils.pb.executor.executor_pb2_grpc as executor_grpc

sys.path.insert(0, os.path.join(root_path, 'utils/pb/order_queue'))
import utils.pb.order_queue.order_queue_pb2 as order_queue
import utils.pb.order_queue.order_queue_pb2_grpc as order_queue_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Exec-%(name)s] %(message)s")
logger = logging.getLogger(__name__)
class ExecutorService(executor_grpc.ExecutorServiceServicer):
    def __init__(self, executor_id, known_ids, queue_host):
        self.id = int(executor_id)
        self.known_ids = [int(i) for i in known_ids.split(',')]
        self.queue_host = queue_host
        self.leader_id = None
        self.is_leader = False
        self.data = { # default data
            "To Kill a Mockingbird" : 2, # title : stock ammount
            "Harry Potter and the Sorcerer's Stone" : 4,
        }
        
        logger.name = str(self.id)
        logger.info(f"Initialized Executor {self.id}. Peers: {self.known_ids}")

    # --- gRPC Server Methods for Bully Algorithm ---
    def Election(self, request, context):
        """Responds to election messages from lower-ID nodes."""
        logger.info(f"Received ELECTION from {request.sender_id}")
        # If someone with a lower ID started an election, we answer OK and start our own
        if request.sender_id < self.id:
            threading.Thread(target=self.start_election).start()
        return executor_pb2.ElectionResponse(ok=True)

    def Coordinator(self, request, context):
        """Accepts the new leader."""
        previous_leader = self.leader_id
        ok = False
        if self.id < request.leader_id:
            ok = True
            if request.become_leader:
                self.leader_id = request.leader_id
                if self.leader_id != request.leader_id:
                    logger.info(f"Node {request.leader_id} is the new COORDINATOR.")
                self.is_leader = False
        elif self.id == request.leader_id:
            pass
        else:
            logger.warning(f"lower node proclaimed leadership")
        return executor_pb2.CoordinatorResponse(ok=ok, previous_leader=previous_leader)

    def Heartbeat(self, request, context):
        """Simple health check response."""
        return executor_pb2.HeartbeatResponse(is_alive=True)
    
    def Read(self, request, context):
        return executor_pb2.ReadResponse(value=self.data.get(request.key))
    
    def Write(self, request, context):
        if request.key is not None and request.value is not None:
            self.data[request.key] = request.value
            return executor_pb2.WriteResponse(success=True)
        return executor_pb2.WriteResponse(success=False)
    
    def GetStock(self, request, context):
        return executor_pb2.StockResponse(all_items=self.data.keys())

    # --- Active Logic ---
    def start_election(self):
        """Implements the Bully Algorithm election process."""
        logger.info("Starting ELECTION...")
        higher_nodes = [node for node in self.known_ids if node > self.id]
        
        if not higher_nodes:
            ok, prevoius_leader = self.proclaim_leadership(True)
            self.become_leader(prevoius_leader)
            return

        answers = 0
        for node_id in higher_nodes:
            try:
                with grpc.insecure_channel(f'executor_{node_id}:50055') as channel:
                    stub = executor_grpc.ExecutorServiceStub(channel)
                    response = stub.Election(executor_pb2.ElectionRequest(sender_id=self.id), timeout=2)
                    if response.ok:
                        answers += 1
            except grpc.RpcError:
                pass # Node is down
        
        if answers == 0:
            ok, prevoius_leader = self.proclaim_leadership(True)
            self.become_leader(prevoius_leader)
        else:
            logger.info("Higher node responded. Waiting for COORDINATOR message.")

    def proclaim_leadership(self, become_leader = False):
        previous_leaders = []
        ok = True
        #logger.info(f"{self.id} proclaiming leadership with become leader: {become_leader}")
        for node_id in self.known_ids:
            try:
                with grpc.insecure_channel(f'executor_{node_id}:50055') as channel:
                    stub = executor_grpc.ExecutorServiceStub(channel)
                    response = stub.Coordinator(executor_pb2.CoordinatorRequest(leader_id=self.id, become_leader=become_leader), timeout=1)
                    if response.previous_leader != 0: # None becomes 0 through grpc call
                        previous_leaders.append(response.previous_leader)
                    if not response.ok:
                        ok = False
            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                    pass
                else:
                    logger.error(f"gRPC error with node {node_id}: {e.code()} - {e.details()}")
            except Exception as e:
                logger.info(f"error during proclamation: {type(e)} {e}")
        previous_leaders.sort()
        if previous_leaders:
            previous_leader = previous_leaders[-1]
        else:
            previous_leader = None
        return ok, previous_leader
    
    def become_leader(self, previous_leader):
        self.is_leader = True
        self.leader_id = self.id
        logger.info(f"*** I AM THE NEW LEADER *** previous leader was {previous_leader}")
        
        if previous_leader:
            self.pull_stock(previous_leader)
            
                
    def pull_stock(self, from_id : int):
        if from_id != self.id and from_id is not None:
            logger.info(f"{self.id} is retrieving stock from {from_id}")
            try:
                with grpc.insecure_channel(f'executor_{from_id}:50055') as channel:
                    stub = executor_grpc.ExecutorServiceStub(channel)
                    response = stub.GetStock(executor_pb2.StockRequest())
                    items = response.all_items
                    for name in items:
                        ammount = stub.Read(executor_pb2.ReadRequest(key=name)).value
                        self.data[name] = ammount
            except Exception as e:
                logger.exception(f"error on stock sync:") # This automatically captures the stack trace

    def run_worker(self):
        """Background thread to process queue (if leader) or check health (if follower)."""
        # Initial election on startup
        time.sleep(2) # Wait for network to establish
        self.start_election()
        while self.leader_id is None or self.leader_id <= 0: # wait untill leader is declared
            pass
        self.pull_stock(self.leader_id) # retrieve stock on startup
        
        while True:
            time.sleep(5)
            if self.is_leader:
                ok, previous_leader = self.proclaim_leadership()
                if not ok:
                    self.start_election()
                    continue
                while self.process_queue(): # process orders untill there are none
                    pass
            else:
                self.check_leader_health()

    def process_queue(self):
        """
        Dequeue and execute orders (Mutual Exclusion achieved by being the sole leader).
        Returns wether an order was processed
        """
        try:
            with grpc.insecure_channel(self.queue_host) as channel:
                stub = order_queue_grpc.OrderQueueServiceStub(channel)
                response = stub.Dequeue(order_queue.DequeueRequest())
                if response.has_order:
                    logger.info(f">>> Executing Order: {response.order_id} <<<")
                    # Here you would actually do the stock updates, payment, etc.
                    items : list[tuple[str, int]] = response.items
                    for item in items:
                        self.data[item.title] = self.data.get(item.title, 0) - item.ammount
                    for node_id in self.known_ids:
                        with grpc.insecure_channel(f'executor_{node_id}:50055') as channel:
                            stub = executor_grpc.ExecutorServiceStub(channel)
                            for item in items:
                                stub.Write(executor_pb2.WriteRequest(key=item.title, value=self.data.get(item.title)))
                    logger.info("completed order: {response.order_id}")
                    return True
        except grpc.RpcError as e:
            logger.error(f"Failed to connect to queue: {e}")
        return False

    def check_leader_health(self):
        if self.leader_id is None or self.leader_id == self.id:
            return
            
        try:
            with grpc.insecure_channel(f'executor_{self.leader_id}:50055') as channel:
                stub = executor_grpc.ExecutorServiceStub(channel)
                stub.Heartbeat(executor_pb2.HeartbeatRequest(leader_id=self.leader_id), timeout=2)
        except grpc.RpcError:
            logger.warning(f"Leader {self.leader_id} is down! Initiating election.")
            self.leader_id = None
            self.start_election()

def serve():
    executor_id = os.getenv("EXECUTOR_ID", "1")
    known_ids = os.getenv("KNOWN_IDS", "")
    queue_host = os.getenv("QUEUE_HOST", "order_queue:50054")

    service = ExecutorService(executor_id, known_ids, queue_host)
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    executor_grpc.add_ExecutorServiceServicer_to_server(service, server)
    server.add_insecure_port("[::]:50055") # Internal port for Bully communication
    server.start()
    
    # Start the active background thread
    threading.Thread(target=service.run_worker, daemon=True).start()
    
    server.wait_for_termination()

if __name__ == '__main__':
    serve()