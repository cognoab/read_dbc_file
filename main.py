import cantools
from typing import Dict, Tuple

# Load the .dbc file
db = cantools.database.load_file('your_file.dbc')

# Dictionary to store modified messages
modified_messages: Dict[int, bytearray] = {}

# Function to split the start bit into start byte and start bit within the byte
def get_start_byte_and_bit(start_bit: int) -> Tuple[int, int]:
    start_byte = start_bit // 8
    start_bit_in_byte = start_bit % 8
    return start_byte, start_bit_in_byte

# Function to update a signal value in a message
def update_signal_value(message: cantools.database.can.Message, signal_name: str, value: int) -> bool:
    for signal in message.signals:
        if signal.name == signal_name:
            start_byte, start_bit_in_byte = get_start_byte_and_bit(signal.start)
            
            # Check if the value fits in the signal length
            if value < 0 or value >= (1 << signal.length):
                print(f'Error: Value {value} does not fit in the signal length of {signal.length} bits.')
                return False

            # Prepare a byte array to hold the data if not already present
            if message.frame_id not in modified_messages:
                modified_messages[message.frame_id] = bytearray(message.length)
            
            data = modified_messages[message.frame_id]
            
            # Insert the value into the appropriate bytes
            value_shifted = value << start_bit_in_byte
            for i in range(signal.length):
                byte_index = start_byte + (start_bit_in_byte + i) // 8
                bit_position = (start_bit_in_byte + i) % 8
                bit_value = (value_shifted >> i) & 1
                data[byte_index] &= ~(1 << bit_position)  # Clear the bit
                data[byte_index] |= (bit_value << bit_position)  # Set the bit

            return True
    return False

# Main loop
while True:
    user_input = input('Enter signal name and value (or type "exit" to quit): ')
    
    if user_input.lower() == 'exit':
        break

    try:
        signal_name, value_str = user_input.split()
        value = int(value_str)
    except ValueError:
        print('Invalid input. Please enter in the format "SignalName Value".')
        continue

    signal_found = False
    for message in db.messages:
        if update_signal_value(message, signal_name, value):
            signal_found = True
            print(f'Signal "{signal_name}" updated in message ID {hex(message.frame_id)}.')
            break
    
    if not signal_found:
        print(f'Signal "{signal_name}" not found in any message.')

    # Print modified messages
    print('\nModified Messages:')
    for message_id, data in modified_messages.items():
        data_str = ', '.join(f'byte {i+1}: {hex(data[i])}' for i in range(len(data)))
        print(f'ID: {hex(message_id)}, {data_str}')

    print('\nReady for next input...')
