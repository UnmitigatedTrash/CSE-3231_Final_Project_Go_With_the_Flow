import random

# Defines a frame
class Frame:
    def __init__(self, seq_num, time_sent):
        self.seq_num = seq_num  # Sequence number of frame
        self.time_sent = time_sent  # Timestamp when frame was sent
        self.unack = True   # Tracks if frame is unacknowledged
    
# Defines an ACK
class ACK:
    def __init__(self, ack_num):
        self.ack_num = ack_num  # Seq num of frame being acknowledged

# Defines a sender node
class SenderNode:
    def __init__(self, sws):
        self.sws = sws  # Sender window size
        self.lar = -1   # Last ack received
        self.lfs = -1   # Last frame sent
        self.frames = []    # List of unacknowledged frames in transit

    # Send a frame
    def send_frame(self, timestamp):
        # Check if a new frame can be sent (the window is not full)
        if (self.lfs - self.lar) >= self.sws:
            return None

        self.lfs += 1   # Slide the window

        frame_to_send = Frame(self.lfs, timestamp)  # Create a new frame with the next sequence number and the current timestamp

        self.frames.append(frame_to_send)   # Add the new frame to the list of unacked frames in transit

        return frame_to_send    # Return the frame to be sent
    
    # Check for timeouts
    def check_timeout(self, timestamp, timeout):
        # Remove frames that have been acknowledged
        self.frames = [f for f in self.frames if f.seq_num > self.lar]
        
        # Iterate through unacknowledged frames
        for frame in self.frames:
            # If a frame has been unacknowledged for longer than timeout
            if frame.unack and timestamp - frame.time_sent >= timeout:
                frame.time_sent = timestamp # Update time sent to the current timestamp

                return frame    # Return frame so it can be retransmitted
    
        return None # No frame needs to be retransmitted

    # Process incoming ACK
    def process_ack(self, ack: ACK):
        # If ACK is corrupted, send error ACK
        if ack.ack_num == '?':
            return ACK('?')

        # Iterate through unacknowledged frames
        for frame in self.frames:
            # If frame's seq num is <= to ACK number, acknowledge it
            if frame.seq_num <= ack.ack_num:
                frame.unack = False

        # Remove acknowledged frames from list of unacknowledged frames
        self.frames = [frame for frame in self.frames if frame.unack]

        # Update last acknowledged frame
        self.lar = max(self.lar, ack.ack_num)

# Defines a reciever node
class ReceiverNode:
    def __init__(self, rws):
        self.rws = rws
        self.laf = rws - 1
        self.lfr = -1
        self.buffer = set()

    # Receive a frame
    def receive_frame(self, frame: Frame):
        # If frame is corrupted, send error ACK
        if is_corrupted(error):
            return ACK('?')
        
        # If frame is out of order
        if not (self.lfr < frame.seq_num <= self.laf):
            return None # Do not send ACK

        # Add frame to buffer
        self.buffer.add(frame.seq_num)

        # Iterate through buffer to find last frame received in order
        while (self.lfr + 1) in self.buffer:
            self.buffer.remove(self.lfr + 1)    # Remove frame from buffer
            self.lfr += 1   # Slide the window
            self.laf = self.lfr + self.rws  # Update largest acceptable frame

        # If no frames are received in order
        if self.lfr < 0:
            return None # Do not send ACK

        return ACK(self.lfr)    # Send ACK for last frame received in order

# Determines if a frame is corrupted
def is_corrupted(error):
    return random.random() < error

# Simulate sliding window
def do_simulation(duration, error, timeout, sender, receiver):
    # Track frame and ACK in transit
    frame_in_transit = None
    ack_in_transit = None
    
    # Simulate sliding window by iterating timestamp
    for timestamp in range(duration):
        # Set error flags to False at the start of each timestamp
        last_frame_error = False
        last_ack_error = False
        
        # Process ack in transit
        if ack_in_transit is not None:
            # If ACK is corrupted
            if ack_in_transit.ack_num == '?':
                last_ack_error = True   # Set ack error flag to True

            sender.process_ack(ack_in_transit)  # Sender processes ACK

            ack_in_transit = None   # Clear ACK in transit after processing

        # Process frame in transit
        if frame_in_transit is not None:
            ack = receiver.receive_frame(frame_in_transit)  # Receiver processes frame and generates ACK

            # If frame is corrupted
            if isinstance(ack, ACK) and ack.ack_num == '?':
                last_frame_error = True # Set frame error flag to True

            # If ACK is corrupted
            if ack is not None and is_corrupted(error):
                ack_in_transit = ACK('?')   # Set ACK in transit to error ACK
                last_ack_error = True   # Set ACK error flag to True
            else:
                ack_in_transit = ack    # Set ACK in transit to ACK sent by receiver

            frame_in_transit = None # Clear frame in transit after processing

        frame = sender.check_timeout(timestamp, timeout)    # Check for timeouts and retransmit frame if needed

        # If frame times out
        if frame is None:
            frame = sender.send_frame(timestamp)    # Resend frame

        frame_in_transit = frame    # Set frame in transit to frame sent by sender

        print(format_output(timestamp, frame, sender, receiver, ack_in_transit, last_frame_error, last_ack_error))  # Print output for current timestamp

# Process and format output for each timestamp
def format_output(timestamp, frame, sender, receiver, ack, last_frame_error, last_ack_error):
    frame_num = '_' if frame is None else frame.seq_num # Print '_' if no frame sent, or show frame number

    # If error in sending ACK
    if last_ack_error:
        lar = '?'   # Print '?' if error
    else:
        lar = '_' if sender.lar == -1 else sender.lar   # Print '_' if no frame acknowledged, or show last ack received

    # If error in sending frame
    if last_frame_error:
        lfs = '?'   # Print '?' if error
    else:
        lfs = '_' if sender.lfs < 0 else sender.lfs # Print '_' if indicate no frame sent, or show last frame sent

    # If error in receiving frame
    if last_frame_error:
        lfr = '?'   # Print '?' if error
    else:
        lfr = '_' if receiver.lfr < 0 else receiver.lfr # Print '_' if indicate no frame received in order, or show last frame received
    
    # If error in receiving ACK
    if last_ack_error:
        ack_num = '?'   # Print '?' if error
    elif ack is None:
        ack_num = '_'   # Print '_' if no ACK sent
    elif ack.ack_num == '?':
        ack_num = '?'   # Print '?' if error
    else:
        ack_num = ack.ack_num   # Print ACK number

    laf = '_' if receiver.lfr < 0 else receiver.laf # Print '_' if no largest acceptable frame, or show largest acceptable frame

    buffer_str = '(' + ', '.join(map(str, sorted(receiver.buffer))) + ')'   # Format buffer as a string

    return f"{timestamp}\t|\t{frame_num}\t{lar}\t{lfs}\t|\t{lfr}\t{laf}\t{ack_num}\t{buffer_str}"   # Return processed and formatted output

# Create sender and receiver nodes
def create_nodes(sws, rws):
    sender = SenderNode(sws)
    receiver = ReceiverNode(rws)

    return sender, receiver

# Print header information
def print_header(duration, sws, rws, error, timeout):
    print("Student Name: Jacob Lebkuecher")
    print("Student ID: 904026388")
    print(f"Parameters: duration={duration} sws={sws} rws={rws} error={error} timeout={timeout}\n")

# Create initial simulation variables
input = str(input("Input parameters: "))   # Get input parameters from user

duration, sws, rws, error, timeout = input.split(' ')   # Parse input parameters

duration = int(duration)   # Duration of simulation
sws = int(sws)   # Sender window size
rws = int(rws)   # Receiver window size
error = float(error)   # Probability of error
timeout = int(timeout)   # Timeout duration

sender, receiver = create_nodes(sws, rws)   # Create sender and receiver nodes

print_header(duration, sws, rws, error, timeout)   # Print header information

do_simulation(duration, error, timeout, sender, receiver)   # Run the simulation