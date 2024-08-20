import cantools
from typing import Dict, Tuple, Optional
from enum import Enum

class Endian(Enum):
    LITTLE_ENDIAN = 'LITTLE_ENDIAN'
    BIG_ENDIAN = 'BIG_ENDIAN'

class CANMessageHandler:
    def __init__(self, dbc_file: str, endian: Endian):
        # Load the .dbc file
        self.db = cantools.database.load_file(dbc_file)
        # Dictionary to store modified messages
        self.modified_messages: Dict[int, bytearray] = {}
        # Set the endianness for the handler
        self.endian = endian

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
                byte_count = (start_bit_in_byte + signal.length + 7) // 8
                for i in range(byte_count):
                    byte_index = start_byte + i
                    byte_mask = (mask >> (i * 8)) & 0xFF
                    data[byte_index] &= ~byte_mask

                # Set the signal value according to the endianness
                value_shifted = value << start_bit_in_byte
                for i in range(byte_count):
                    if self.endian == Endian.LITTLE_ENDIAN:
                        byte_index = start_byte + i
                    else:
                        byte_index = start_byte + byte_count - 1 - i
                    byte_value = (value_shifted >> (i * 8)) & 0xFF
                    data[byte_index] |= byte_value

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
            print(f'Message Name: {message.name:<20} ID: {hex(message.frame_id):<10} ({message.frame_id:<5})')
            for signal in message.signals:
                start_byte, start_bit_in_byte = self.get_start_byte_and_bit(signal.start)
                current_value = self.get_signal_value(message.frame_id, signal)
                value_str = f'Current Value: {current_value}' if current_value is not None else 'Not modified'
                print(f'  Signal Name: {signal.name:<25} Start Byte: {start_byte:<3} Start Bit: {start_bit_in_byte:<3} Length: {signal.length:<3} {value_str}')
        print()

    def print_modified_messages(self):
        if not self.modified_messages:
            print('No messages have been modified yet.')
            return
        
        print('\nModified CAN Messages:')
        for message_id, data in self.modified_messages.items():
            message = self.db.get_message_by_frame_id(message_id)
            print(f'Message Name: {message.name:<20} ID: {hex(message_id):<10} ({message_id:<5})')
            for signal in message.signals:
                current_value = self.get_signal_value(message_id, signal)
                if current_value is not None:
                    start_byte, start_bit_in_byte = self.get_start_byte_and_bit(signal.start)
                    print(f'  Signal Name: {signal.name:<25} Start Byte: {start_byte:<3} Start Bit: {start_bit_in_byte:<3} Length: {signal.length:<3} Current Value: {current_value}')
        print()

    def print_modified_data(self):
        if not self.modified_messages:
            print('No messages have been modified yet.')
            return
        
        print('\nModified CAN Message Data:')
        for message_id, data in self.modified_messages.items():
            message = self.db.get_message_by_frame_id(message_id)
            print(f'Message: {message.name:<20} ID: {hex(message_id):<10} ({message_id:<5})')
            for i, byte in enumerate(data):
                binary_representation = f'{byte:08b}'
                print(f'  Data {i+1:<3}: 0x{byte:02X} ({binary_representation})')
        print()

    def search_message_by_id(self, id_str: str):
        try:
            # Check if the ID is in hexadecimal format (e.g., "0x123")
            if id_str.lower().startswith('0x'):
                search_id = int(id_str, 16)
            else:
                # Otherwise, assume it's a decimal ID
                search_id = int(id_str)
        except ValueError:
            print(f'Invalid ID format: {id_str}')
            return

        message = self.db.get_message_by_frame_id(search_id)
        if message:
            print(f'\nMessage Found: {message.name:<20} ID: {hex(message.frame_id):<10} ({message.frame_id:<5})')
            for signal in message.signals:
                start_byte, start_bit_in_byte = self.get_start_byte_and_bit(signal.start)
                current_value = self.get_signal_value(message.frame_id, signal)
                value_str = f'Current Value: {current_value}' if current_value is not None else 'Not modified'
                print(f'  Signal Name: {signal.name:<25} Start Byte: {start_byte:<3} Start Bit: {start_bit_in_byte:<3} Length: {signal.length:<3} {value_str}')
        else:
            print(f'No message found with ID {id_str}.')

    def handle_input(self, user_input: str):
        if user_input.upper() == 'A':
            self.print_all_messages()
        elif user_input.upper() == 'L':
            self.print_modified_messages()
        elif user_input.upper() == 'D':
            self.print_modified_data()
        elif user_input.upper().startswith('S '):
            _, id_str = user_input.split(maxsplit=1)
            self.search_message_by_id(id_str)
        else:
            try:
                signal_name, value_str = user_input.split()
                if value_str.lower().startswith('0x'):
                    value = int(value_str, 16)
                else:
                    value = int(value_str)
            except ValueError:
                print('Invalid input. Please enter in the format "SignalName Value", e.g., "SIGNAL_01 0x20".')
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
    endian_choice = input('Choose endian type (LITTLE_ENDIAN/BIG_ENDIAN): ').strip().upper()
    endian = Endian.LITTLE_ENDIAN if endian_choice == 'LITTLE_ENDIAN' else Endian.BIG_ENDIAN

    handler = CANMessageHandler('your_file.dbc', endian)
    
    while True:
        user_input = input('Enter signal name and value, or type "A" to show all messages, "L" to show modified messages, "D" to show modified data, "S [id]" to search by ID, "Q" to quit: ').strip()
        
        if user_input.lower() == 'q':
            break

        handler.handle_input(user_input)
        print('\nReady for next input...')


if __name__ == '__main__':
    main()
