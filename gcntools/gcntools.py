# gCn Tools
# A software library that makes interacting with gCn (global CALCnet)
# for TI-83/84+ (SE) calculators much easier.

# Gregory "ElectronicsGeek" Parker 2014
# (Special thanks to Christopher "KermMartian" Mitchell, Thomas
# "elfprince13" Dickerson and many others for helpful hints along the
# way :D)

import xml.etree.ElementTree as ET

class TokenTools(object):
    
    def __init__(self):
        tree = ET.parse("Tokens.xml")
        root = tree.getroot()
        ET.register_namespace("","http://merthsoft.com/Tokens")
        
        self.tokens = {} # Empty list to be filled by tokens
        
        # Tokens composed of two bytes (eg. accents, lowercase letters)
        self.two_byte_tokens = {}
        
        # dbtokens = double byte tokens - The first byte of each double
        # byte token. Used internally for checking whether or not a byte
        # is a double byte.
        self.__dbtokens = (0x5C, 0x5D, 0x5E, 0x60, 0x61, 0x62, 0x63,
                           0x7E, 0xAA, 0xBB, 0xEF)
        
        for token in root.findall("{http://merthsoft.com/Tokens}Token"):
            string = token.get("string")
            byte = int(token.get("byte").replace("$", "0x"),16)
            
            # If the byte doesn't have a string attatched to it in the
            # XML file, it's a double byte.
            if not string:
                for child in token.findall(
                "{http://merthsoft.com/Tokens}Token"):
                    sub_string = child.get("string")
                    
                    # Convert string of byte into integer by removing
                    # Tokens.xml's formatting
                    sub_byte = int(child.get("byte").replace("$", "0x"),16)
                    self.two_byte_tokens[byte,sub_byte] = sub_string
                    
            else:
                self.tokens[byte] = string

    def detokenize(self, byte_string):
        """Turns a calculator string into a computer readable one."""
        index = 0
        outstring = ""
        
        while index < len(byte_string):
            current_byte = ord(byte_string[index])
            
            if current_byte in self.__dbtokens and index + 1 < \
            len(byte_string):
                next_byte = ord(byte_string[index + 1])
                outstring += self.two_byte_tokens[current_byte, next_byte]
                index += 1
                
            else:
                outstring += self.tokens[current_byte]
            
            index += 1
            
        return outstring
            
    def tokenize(self, string):
        """Turns a computer formatted string into a calculator readable 
        one."""
        
        index = len(string)
        outtokens = []
        string_copy = string[:]
        
        while index != 0:
            istoken = self.__find_key(self.tokens,string_copy[:index])
            is2bytetoken = self.__find_key(self.two_byte_tokens,string_copy[:index])
            
            if istoken:
                outtokens.append(istoken)
                string_copy = self.__del_str(string_copy, index)
                index = len(string_copy)
                
            elif is2bytetoken:
                # 2 byte tokens always come in pairs, ergo both elements
                # are appended to outtokens
                outtokens.append(is2bytetoken[0])
                outtokens.append(is2bytetoken[1])
                string_copy = self.__del_str(string_copy, index)
                index = len(string_copy)
                
            else:
                index -= 1
                
        outtokens_bytearray = bytearray(outtokens)
        return outtokens_bytearray # Tokenized string is returned
                
    ### INTERNAL METHODS (Used in tokenize method)            
            
    def __find_key(self, dictionary, target):
        """Finds a key in the specified dictionary"""
        for key in dictionary.keys():
            if dictionary[key] == target:
                return key
    
    def __del_str(self, string, index):
        """Deletes a slice of string"""
        b = bytearray(string)
        del b[:index]
        s = str(b)
        return s
