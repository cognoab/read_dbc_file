import cantools
from typing import Dict, Tuple

class CANMessageHandler:
    def __init__(self, dbc_file: str):
        # Load the .dbc file
        self.db = cantools.database.load_file(dbc_file)
        # Dictionary to store modified messages
        self.modified_messages: Dict[int, bytearray] = {}

    def get_start_byte_and_bit(self, start_bit: int) -> Tuple[int, int]:
        start_byte = start_bit // 8
        start_bit_in_byte = start_bit % 8
        return start_byte, start_bit_in_byte

    def update_signal_value(self, message: cantools.database.can.Message, signal_name: str, value: int) -> bool:
        for signal in message.signals:
            if signal.name == signal_name:
                start_byte, start_bit_in_byte = self.get_start_byte_and_bit(signal.start)
                
                # Check if the value fits in the signal length
                if value < 0 or value >= (1 << signal.length):
                    print(f'Error: Value {value} does not fit in the signal length of {signal.length} bits.')
                    return False

                # Prepare a byte array to hold the data if not already present
                if message.frame_id not in self.modified_messages:
                    self.modified_messages[message.frame_id] = bytearray(message.length)
                
                data = self.modified_messages[message.frame_id]
                
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

    def print_all_messages(self):
        print('\nAll CAN Messages:')
        for message in self.db.messages:
            data_str = ', '.join(f'byte {i+1}: 0x00' for i in range(message.length))
            print(f'ID: {hex(message.frame_id)}, {data_str}')
        print()

    def print_modified_messages(self):
        print('\nModified CAN Messages:')
        for message_id, data in self.modified_messages.items():
            data_str = ', '.join(f'byte {i+1}: {hex(data[i])}' for i in range(len(data)))
            print(f'ID: {hex(message_id)}, {data_str}')
        print()

    def handle_input(self, user_input: str):
        if user_input.upper() == 'A':
            self.print_all_messages()
        elif user_input.upper() == 'L':
            self.print_modified_messages()
        else:
            try:
                signal_name, value_str = user_input.split()
                value = int(value_str)
            except ValueError:
                print('Invalid input. Please enter in the format "SignalName Value".')
                return

            signal_found = False
            for message in self.db.messages:
                if self.update_signal_value(message, signal_name, value):
                    signal_found = True
                    print(f'Signal "{signal_name}" updated in message ID {hex(message.frame_id)}.')
                    break
            
            if not signal_found:
                print(f'Signal "{signal_name}" not found in any message.')


def main():
    handler = CANMessageHandler('your_file.dbc')
    
    while True:
        user_input = input('Enter signal name and value, or type "A" to show all messages, "L" to show modified messages, "Q" to quit: ').strip()
        
        if user_input.lower() == 'q':
            break

        handler.handle_input(user_input)
        print('\nReady for next input...')


if __name__ == '__main__':
    main()
