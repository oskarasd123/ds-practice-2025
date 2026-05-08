import sys
import os
import time
import threading
import grpc
from concurrent import futures
import logging

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
root_path = os.path.abspath(os.path.join(FILE, '../../..'))

sys.path.insert(0, os.path.join(root_path, 'utils/pb/executor'))
import executor_pb2 as executor_pb2
import executor_pb2_grpc as executor_grpc

sys.path.insert(0, os.path.join(root_path, 'utils/pb/order_queue'))
import order_queue_pb2 as order_queue
import order_queue_pb2_grpc as order_queue_grpc

sys.path.insert(0, os.path.join(root_path, 'utils/pb/payment'))
import payment_pb2 as payment
import payment_pb2_grpc as payment_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Exec-%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)

EXECUTOR_PORT = os.getenv("EXECUTOR_PORT")
if EXECUTOR_PORT is None:
    raise RuntimeError("EXECUTOR_PORT environment variable is required!")


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
            if self.leader_id == request.leader_id:
                ok = True
            if request.become_leader:
                ok = True
                if self.leader_id != request.leader_id:
                    logger.info(f"Node {request.leader_id} is the new COORDINATOR.")
                self.leader_id = request.leader_id
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
                if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED or e.code() == grpc.StatusCode.UNAVAILABLE:
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
        while self.leader_id is None or self.leader_id == 0: # wait untill leader is declared
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
        Dequeue and execute orders using 2-Phase Commit (2PC).
        Returns whether an order was processed.
        """
        try:
            with grpc.insecure_channel(self.queue_host) as channel:
                stub = order_queue_grpc.OrderQueueServiceStub(channel)
                response = stub.Dequeue(order_queue.DequeueRequest())
                
                if response.has_order:
                    order_id = response.order_id
                    logger.info(f">>> Executing Order: {order_id} <<<")
                    
                    items = response.items # This is a repeated field of item objects
                    
                    # ==========================================
                    # PHASE 1: PREPARE
                    # ==========================================
                    votes = []
                    
                    # 1. Prepare Local Database (Check stock for all items)
                    db_ready = True
                    for item in items:
                        current_stock = self.data.get(item.title, 0)
                        if current_stock < item.ammount: # Check if we have enough stock
                            db_ready = False
                            logger.warning(f"[2PC-Phase 1] DB Prepare: Voted NO (Out of stock: {item.title})")
                            break
                    
                    if db_ready:
                        logger.info(f"[2PC-Phase 1] DB Prepare: Voted YES for {order_id}")
                    votes.append(db_ready)

                    # 2. Prepare Payment Service
                    try:
                        with grpc.insecure_channel('payment:50055') as pay_chan:
                            pay_stub = payment_grpc.PaymentServiceStub(pay_chan)
                            pay_resp = pay_stub.Prepare(payment.PrepareRequest(order_id=str(order_id)))
                            logger.info(f"[2PC-Phase 1] Payment Prepare: Voted {'YES' if pay_resp.ready else 'NO'}")
                            votes.append(pay_resp.ready)
                    except Exception as e:
                        logger.error(f"[2PC-Phase 1] Payment Prepare: Failed ({e})")
                        votes.append(False)

                    # ==========================================
                    # PHASE 2: COMMIT OR ABORT
                    # ==========================================
                    if all(votes) and len(votes) == 2:
                        # COMMIT
                        logger.info(f"[2PC-Phase 2] All voted YES. Committing transaction {order_id}...")
                        
                        # Commit DB locally (deduct stock)
                        for item in items:
                            self.data[item.title] = self.data.get(item.title, 0) - item.ammount
                            logger.info(f"Database updated. New stock for '{item.title}': {self.data[item.title]}")
                        
                        # Replicate DB changes to followers (using your teammate's logic)
                        for node_id in self.known_ids:
                            # Skip sending to self
                            if node_id == self.id:
                                continue
                            try:
                                with grpc.insecure_channel(f'executor_{node_id}:50055') as channel:
                                    rep_stub = executor_grpc.ExecutorServiceStub(channel)
                                    for item in items:
                                        rep_stub.Write(executor_pb2.WriteRequest(key=item.title, value=self.data.get(item.title)))
                            except Exception as e:
                                logger.error(f"Failed to replicate to executor_{node_id}: {e}")
                                
                        # Commit Payment
                        try:
                            with grpc.insecure_channel('payment:50055') as pay_chan:
                                pay_stub = payment_grpc.PaymentServiceStub(pay_chan)
                                pay_stub.Commit(payment.CommitRequest(order_id=str(order_id)))
                        except Exception as e:
                            logger.error(f"Failed to commit payment: {e}")
                            
                        logger.info(f">>> Order {order_id} SUCCESSFULLY EXECUTED <<<")
                    else:
                        # ABORT
                        logger.warning(f"[2PC-Phase 2] Transaction aborted for order {order_id}.")
                        
                        # Abort Payment (DB doesn't need abort logic since we didn't deduct anything yet)
                        try:
                            with grpc.insecure_channel('payment:50055') as pay_chan:
                                pay_stub = payment_grpc.PaymentServiceStub(pay_chan)
                                pay_stub.Abort(payment.AbortRequest(order_id=str(order_id)))
                        except Exception as e:
                            pass

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
    server.add_insecure_port(f"[::]:{EXECUTOR_PORT}")
    server.start()
    
    threading.Thread(target=service.run_worker, daemon=True).start()
    
    server.wait_for_termination()

if __name__ == '__main__':
    serve()