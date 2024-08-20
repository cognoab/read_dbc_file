import cantools
from typing import Dict, Optional
from colorama import Fore, Style, init
import traceback
# Initialize colorama
init(autoreset=True)

CAN_DB = './CANsignal.dbc'

class CANMessageHandler:
    def __init__(self, dbc_file: str):
        # Load the .dbc file
        self.db = cantools.database.load_file(dbc_file)
        # Dictionary to store modified signal values by message ID
        self.modified_messages: Dict[int, Dict[str, int]] = {}

    def find_message_by_signal(self, signal_name: str) -> Optional[str]:
        for message in self.db.messages:
            if any(signal.name == signal_name for signal in message.signals):
                return message.name
        return None

    def get_signal_display_value(self, signal, value: int) -> str:
        """Returns the display string for a signal value, using its choices if available."""
        if signal.choices and value in signal.choices:
            return f'{value} ({signal.choices[value]})'
        actual_value = value * signal.scale + signal.offset
        return f'{value} ({actual_value})'

    def update_signal_value(self, signal_name: str, value: float) -> bool:
        """Sets the signal's value considering its scale and offset."""
        message_name = self.find_message_by_signal(signal_name)
        if not message_name:
            print(f'Signal "{signal_name}" not found in any message.')
            return False
        
        message = self.db.get_message_by_name(message_name)
        signal = next((s for s in message.signals if s.name == signal_name), None)
        if not signal:
            print(f'Signal "{signal_name}" not found in message "{message_name}".')
            return False

        # Calculate the raw value considering scale and offset
        raw_value = int((value - signal.offset) / signal.scale)

        # Check if the raw value fits within the signal length
        max_value = (1 << signal.length) - 1
        if raw_value < 0 or raw_value > max_value:
            print(f'Error: Value {value} does not fit within the signal length of {signal.length} bits after scaling. Max allowed raw value is {max_value}.')
            return False

        # Update the signal raw value in the dictionary
        if message.frame_id not in self.modified_messages:
            self.modified_messages[message.frame_id] = {}
        
        self.modified_messages[message.frame_id][signal_name] = raw_value
        print(f'Signal "{signal_name}" updated to actual value {value} (raw value {raw_value}) in message ID {hex(message.frame_id)}.')
        return True

    def update_signal_raw_value(self, signal_name: str, raw_value: int) -> bool:
        """Sets the signal's raw value directly without considering scale and offset."""
        message_name = self.find_message_by_signal(signal_name)
        if not message_name:
            print(f'Signal "{signal_name}" not found in any message.')
            return False
        
        message = self.db.get_message_by_name(message_name)
        signal = next((s for s in message.signals if s.name == signal_name), None)
        if not signal:
            print(f'Signal "{signal_name}" not found in message "{message_name}".')
            return False

        # Check if the raw value fits within the signal length
        max_value = (1 << signal.length) - 1
        if raw_value < 0 or raw_value > max_value:
            print(f'Error: Raw value {raw_value} does not fit within the signal length of {signal.length} bits. Max allowed raw value is {max_value}.')
            return False

        # Update the signal raw value in the dictionary
        if message.frame_id not in self.modified_messages:
            self.modified_messages[message.frame_id] = {}
        
        self.modified_messages[message.frame_id][signal_name] = raw_value
        print(f'Signal "{signal_name}" raw value updated to {raw_value} in message ID {hex(message.frame_id)}.')
        return True

    def print_signal_choices(self, signal):
        """Prints the possible choices for a signal."""
        if signal.choices:
            print('    Choices:')
            for value, description in signal.choices.items():
                print(f'      {value}: {description}')

    def print_modified_messages(self):
        if not self.modified_messages:
            print('No messages have been modified yet.')
            return
        
        print('\nModified CAN Messages:')
        for message_id, modified_signals in self.modified_messages.items():
            message = self.db.get_message_by_frame_id(message_id)
            
            # Get the current message data with default signal values
            try:
                raw_data = bytearray(message.length)
                default_data = self.db.decode_message(message.name, raw_data)
            except Exception as e:
                print(f"Error decoding message '{message.name}': {e}")
                default_data = {signal.name: 0 for signal in message.signals}
            
            # Update default data with modified signals
            all_signals = {**default_data, **modified_signals}

            # Encode the message with the full set of signals
            encoded_data = self.db.encode_message(message.name, all_signals)

            # Print message details like in "A", but only for modified messages
            print(f'{Fore.GREEN}Message: {message.name:<31} ID: {hex(message_id)} ({message_id}){Style.RESET_ALL}')
            for signal in message.signals:
                raw_value = all_signals[signal.name]
                actual_value = raw_value * signal.scale + signal.offset
                value_str = f'{raw_value} ({actual_value})'
                modified_str = 'Modified' if signal.name in modified_signals else 'Default '
                print(f'{Fore.CYAN}  Signal: {signal.name:<25} Start Byte: {signal.start // 8:<3} Start Bit: {signal.start % 8:<3} Length: {signal.length:<3} {modified_str}: {value_str}{Style.RESET_ALL}')
            print(f'  Encoded Data:')
            for i, byte in enumerate(encoded_data):
                print(f'    Data {i+1:<3}: 0x{byte:02X} ({byte:08b})')
        print()

    def get_signal_value(self, message_id: int, signal: cantools.database.can.Signal) -> Optional[int]:
        if message_id in self.modified_messages:
            data = self.db.encode_message(self.db.get_message_by_frame_id(message_id).name, self.modified_messages[message_id])
            start_byte = signal.start // 8
            start_bit_in_byte = signal.start % 8
            value = 0
            for i in range(signal.length):
                byte_index = start_byte + (start_bit_in_byte + i) // 8
                bit_position = (start_bit_in_byte + i) % 8
                value |= ((data[byte_index] >> bit_position) & 1) << i
            return value
        return None

    def handle_input(self, user_input: str):
        if user_input.upper() == 'A':
            self.print_all_messages()
        elif user_input.upper() == 'L':
            self.print_modified_messages()
        elif user_input.upper().startswith('S '):
            search_query = user_input[2:].strip()
            self.search_messages(search_query)
        else:
            try:
                data = user_input.split()
                if len(data) == 2:
                    signal_name, value_str = data
                    if value_str.lower().startswith('0x'):
                        value = int(value_str, 16)
                    else:
                        value = int(value_str)
                    self.update_signal_raw_value(signal_name, value)
                elif len(data) == 3:
                    command, signal_name, value_str = data
                    if value_str.lower().startswith('0x'):
                        value = int(value_str, 16)
                    else:
                        value = int(value_str)
                    if command.upper() == 'V':
                        self.update_signal_value(signal_name, value)
            
            except ValueError as ex:
                print('Invalid input. Please enter in the format "V SignalName Value" for actual value or "SignalName Value" for raw value.')
                traceback.print_exception(ex)
                return

    def print_all_messages(self):
        print('\nAll CAN Messages:')
        for message in self.db.messages:
            print('-' * 50)
            print(f'{Fore.GREEN}Message: {message.name:<31} ID: {hex(message.frame_id)} ({message.frame_id}){Style.RESET_ALL}')
            for signal in message.signals:
                print(f'{Fore.CYAN}  Signal: {signal.name:<25} Start Byte: {signal.start // 8:<3} Start Bit: {signal.start % 8:<3} Length: {signal.length:<3}{Style.RESET_ALL}')
        print()

    def search_messages(self, search_query: str):
        print(f'\nSearch Results for "{search_query}":')
        search_query_lower = search_query.lower()
        found = False

        for message in self.db.messages:
            message_name = message.name.lower()
            message_id_hex = hex(message.frame_id).lower()
            message_id_dec = str(message.frame_id)

            if (search_query_lower in message_name or
                search_query_lower in message_id_hex or
                search_query_lower in message_id_dec):
                found = True
                self.print_message_details(message)
                continue

            for signal in message.signals:
                signal_name = signal.name.lower()
                if search_query_lower in signal_name:
                    found = True
                    self.print_message_details(message)
                    break

        if not found:
            print(f'No matches found for "{search_query}".')

    def print_message_details(self, message):
        print('-' * 50)
        print(f'\n{Fore.GREEN}Message: {message.name:<30} ID: {hex(message.frame_id)} ({message.frame_id}){Style.RESET_ALL}')
        for signal in message.signals:
            print(f'{Fore.CYAN}  Signal: {signal.name:<25} Start Byte: {signal.start // 8:<3} Start Bit: {signal.start % 8:<3} Length: {signal.length:<3}{Style.RESET_ALL}')
            self.print_signal_choices(signal)

def main():
    handler = CANMessageHandler(CAN_DB)
    
    while True:
        print('-' * 100)
        user_input = input('Enter "V SignalName Value" to set actual value, "SignalName Value" to set raw value, or type "A" to show all messages, "L" to show modified messages, "S [search_query]" to search by name/ID/signal, "Q" to quit: ').strip()
        
        if user_input.lower() == 'q':
            break

        handler.handle_input(user_input)
        print('\nReady for next input...')


if __name__ == '__main__':
    main()
