import cantools
from typing import Dict, Tuple, Optional

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

                # Clear the bits corresponding to the signal
                mask = ((1 << signal.length) - 1) << start_bit_in_byte
                for i in range(start_byte, start_byte + (start_bit_in_byte + signal.length + 7) // 8):
                    data[i] &= ~(mask & 0xFF)
                    mask >>= 8

                # Set the signal value
                value <<= start_bit_in_byte
                for i in range(start_byte, start_byte + (start_bit_in_byte + signal.length + 7) // 8):
                    data[i] |= (value & 0xFF)
                    value >>= 8

                return True
        return False

    def get_signal_value(self, message_id: int, signal: cantools.database.can.Signal) -> Optional[int]:
        if message_id in self.modified_messages:
            data = self.modified_messages[message_id]
            start_byte, start_bit_in_byte = self.get_start_byte_and_bit(signal.start)
            value = 0
            for i in range(signal.length):
                byte_index = start_byte + (start_bit_in_byte + i) // 8
                bit_position = (start_bit_in_byte + i) % 8
                value |= ((data[byte_index] >> bit_position) & 1) << i
            return value
        return None

    def print_all_messages(self):
        print('\nAll CAN Messages:')
        for message in self.db.messages:
            print(f'Message Name: {message.name}, ID: {hex(message.frame_id)}')
            for signal in message.signals:
                start_byte, start_bit_in_byte = self.get_start_byte_and_bit(signal.start)
                current_value = self.get_signal_value(message.frame_id, signal)
                value_str = f'Current Value: {current_value}' if current_value is not None else 'Not modified'
                print(f'  Signal Name: {signal.name}, Start Byte: {start_byte}, Start Bit: {start_bit_in_byte}, Length: {signal.length}, {value_str}')
        print()

    def print_modified_messages(self):
        if not self.modified_messages:
            print('No messages have been modified yet.')
            return
        
        print('\nModified CAN Messages:')
        for message_id, data in self.modified_messages.items():
            message = self.db.get_message_by_frame_id(message_id)
            print(f'Message Name: {message.name}, ID: {hex(message_id)}')
            for signal in message.signals:
                current_value = self.get_signal_value(message_id, signal)
                if current_value is not None:
                    start_byte, start_bit_in_byte = self.get_start_byte_and_bit(signal.start)
                    print(f'  Signal Name: {signal.name}, Start Byte: {start_byte}, Start Bit: {start_bit_in_byte}, Length: {signal.length}, Current Value: {current_value}')
        print()

    def print_modified_data(self):
        if not self.modified_messages:
            print('No messages have been modified yet.')
            return
        
        print('\nModified CAN Message Data:')
        for message_id, data in self.modified_messages.items():
            message = self.db.get_message_by_frame_id(message_id)
            print(f'Message: {message.name}')
            for i, byte in enumerate(data):
                binary_representation = f'{byte:08b}'
                print(f'  Data {i+1}: 0x{byte:02X} ({binary_representation})')
        print()

    def handle_input(self, user_input: str):
        if user_input.upper() == 'A':
            self.print_all_messages()
        elif user_input.upper() == 'L':
            self.print_modified_messages()
        elif user_input.upper() == 'D':
            self.print_modified_data()
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
        user_input = input('Enter signal name and value, or type "A" to show all messages, "L" to show modified messages, "D" to show modified data, "Q" to quit: ').strip()
        
        if user_input.lower() == 'q':
            break

        handler.handle_input(user_input)
        print('\nReady for next input...')


if __name__ == '__main__':
    main()
