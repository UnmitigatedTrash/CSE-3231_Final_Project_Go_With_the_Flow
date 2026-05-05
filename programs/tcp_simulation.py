import random
import matplotlib.pyplot as plt

# Defines a frame
class Frame:
    def __init__(self, seq_num, time_sent):
        self.seq_num = seq_num  # Sequence number of frame
        self.time_sent = time_sent  # Timestamp when frame was sent
        self.unack = True   # Tracks if frame is unacknowledged
    
# Defines an ACK
class ACK:
    def __init__(self, ack_num, rwnd = 0):
        self.ack_num = ack_num  # Seq num of frame being acknowledged
        self.rwnd = rwnd

# Defines a sender node
class SenderNode:
    def __init__(self, sws):
        self.sws = sws  # Sender window size
        self.cwnd = 1   # Congestion window size
        self.rwnd = -1 # Receiver window size that was advertised
        self.lar = -1   # Last ack received
        self.lfs = -1   # Last frame sent
        self.frames = []    # List of unacknowledged frames in transit
        self.ssthresh = 16  # Connection threshold
        self.state = "slow_start" # Congestion window state
        self.dup_ack_count = 0  # Track duplicate ACK count
        self.last_ack = -1  # Track the last ACK

    # Send a frame
    def send_frame(self, timestamp):
        # Check if a new frame can be sent (the window is not full)
        effective_window = min(self.cwnd, self.rwnd if self.rwnd != -1 else self.sws, self.sws)
        if (self.lfs - self.lar) >= effective_window:
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
                self.on_timeout()

                frame.time_sent = timestamp # Update time sent to the current timestamp

                return frame    # Return frame so it can be retransmitted
    
        return None # No frame needs to be retransmitted

    # Process incoming ACK
    def process_ack(self, ack: ACK, timestamp):
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

        self.rwnd = ack.rwnd

        # If the ACK is a duplicate
        if ack.ack_num == self.last_ack:
            self.dup_ack_count += 1     # Increment duplicate ACK count

            # If the duplicate ACK count is 3, detect packet loss
            if self.dup_ack_count == 3:
                self.on_duplicate_ack()

                missing_frame = self.last_ack + 1   # Retransmit the frame after last ACK

                # Iterate through unacknowledged frames
                for frame in self.frames:
                    # If frame is the missing frame, retransmit the frame
                    if frame.seq_num == missing_frame:
                        frame.time_sent = timestamp     # Update time sent to the current timestamp
        # If the ACK is new
        else:
            self.dup_ack_count = 0      # Set duplicate ACK count to 0
            self.last_ack = ack.ack_num     # Update last ACK received

            # Congestion state 'slow_start', congestion window grows exponentially
            if self.state == "slow_start":
                self.cwnd *= 2  # Increment congestion window size by 1, doubling every RTT

                # If threshold is reached, transition to congestion state 'avoidance'
                if self.cwnd >= self.ssthresh:
                    self.state = "avoidance"
            # Congestion state 'avoidance', congestion window grows linearly
            elif self.state == "avoidance":
                self.cwnd += 1 / self.cwnd
        
    def on_timeout(self):
        # Only half the threshold if the cwnd hasn't been set to 1 yet
        if self.cwnd > 1:
            self.ssthresh = max(self.cwnd // 2, 2)
        self.cwnd = 1
        self.state = "slow_start"

    # Logic for duplicate ACKs. Cuts the window size in half and moves to the avoidance state
    def on_duplicate_ack(self):
        self.ssthresh = max(self.cwnd / 2, 2)
        self.cwnd = self.ssthresh
        self.state = "avoidance"

# Defines a reciever node
class ReceiverNode:
    def __init__(self, rws):
        self.rws = rws
        self.laf = rws - 1
        self.lfr = -1
        self.buffer = set()

    # Receive a frame
    def receive_frame(self, frame: Frame):
        # Frame is older than what we've already received — send duplicate ACK
        if frame.seq_num <= self.lfr:
            return ACK(self.lfr, self.available_window())
    
        # Frame is beyond our window — drop it silently
        if frame.seq_num > self.laf:
            return None
    
        # Frame is in the acceptable range
        self.buffer.add(frame.seq_num)
    
        while (self.lfr + 1) in self.buffer:
            self.buffer.remove(self.lfr + 1)
            self.lfr += 1
            self.laf = self.lfr + self.rws
    
        if self.lfr < 0:
            return None
    
        return ACK(self.lfr, self.available_window())
    
    def available_window(self):
        return max(0, self.rws - len(self.buffer))

# Determines if a frame is corrupted
def is_corrupted(error):
    return random.random() < error

# Simulate sliding window
def do_simulation(duration, error, timeout, sender, receiver):
    # Track frame and ACK in transit
    frame_in_transit : Frame = None
    ack_in_transit : ACK = None

    # Data collection for plotting
    history = {
        'time': [],
        'cwnd': [],
        'ssthresh': [],
        'rwnd': [],
        'ack_num': [],
        'buffer_used': [],
        'effective_window': []
    }
    
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

            sender.process_ack(ack_in_transit, timestamp)  # Sender processes ACK

            ack_in_transit = None   # Clear ACK in transit after processing

        # Process frame in transit
        if frame_in_transit is not None:
            if is_corrupted(error):
                ack = None  # Frame lost — receiver never got it, no ACK generated
                last_frame_error = True
            else:
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
        #print(f"  [debug] cwnd={sender.cwnd:.2f} ssthresh={sender.ssthresh}") #Debug
        print(format_output(timestamp, frame, sender, receiver, ack_in_transit, last_frame_error, last_ack_error))  # Print output for current timestamp
        
        # Record state for plotting
        history['time'].append(timestamp)
        history['cwnd'].append(sender.cwnd)
        history['ssthresh'].append(sender.ssthresh)
        history['rwnd'].append(sender.rwnd if sender.rwnd > 0 else 0)
        history['ack_num'].append(sender.lar if sender.lar >= 0 else 0)
        history['buffer_used'].append(len(receiver.buffer))
        history['effective_window'].append(min(sender.cwnd, sender.rwnd if sender.rwnd > 0 else sender.cwnd, sender.sws))

    return history

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
    print("Group: Go With the Flow")
    print("Student Names: Ethan Van Brunt (ID: 904031060), Ryan Giacoboni (ID: 904003021), Jacob Lebkuecher (ID: 904026388)")
    print(f"Parameters: duration={duration} sws={sws} rws={rws} error={error} timeout={timeout}\n")

def plot_results(history, params):
    duration, sws, rws, error, timeout = params
    
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(f'TCP Simulation (sws={sws}, rws={rws}, error={error}, timeout={timeout})', fontsize=14)
    
    # --- Subplot 1: Congestion control sawtooth ---
    axes[0].plot(history['time'], history['cwnd'], label='cwnd', color='blue', linewidth=2)
    axes[0].plot(history['time'], history['ssthresh'], label='ssthresh', color='orange', linestyle='--')
    axes[0].set_ylabel('Window Size (frames)')
    axes[0].set_title('Congestion Control')
    axes[0].legend(loc='upper right')
    axes[0].grid(True, alpha=0.3)
    
    # --- Subplot 2: Flow control ---
    axes[1].plot(history['time'], history['rwnd'], label='rwnd (advertised)', color='green', linewidth=2)
    axes[1].plot(history['time'], history['buffer_used'], label='buffer used', color='red', linestyle='--')
    axes[1].plot(history['time'], history['effective_window'], label='effective window', color='purple', alpha=0.6)
    axes[1].set_ylabel('Frames')
    axes[1].set_title('Flow Control')
    axes[1].legend(loc='upper right')
    axes[1].grid(True, alpha=0.3)
    
    # --- Subplot 3: ACKs ---
    axes[2].step(history['time'], history['ack_num'], where='post', color='purple', linewidth=1.5)
    axes[2].set_ylabel('ACK Number')
    axes[2].set_xlabel('Time')
    axes[2].set_title('Cumulative ACKs')
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('tcp_simulation.png', dpi = 100, bbox_inches='tight')
    plt.show()

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

history = do_simulation(duration, error, timeout, sender, receiver)   # Run the simulation
plot_results(history, (duration, sws, rws, error, timeout))
