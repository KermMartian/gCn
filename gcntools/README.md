# gcntools

### What is it
A software library that makes interacting with gCn (global CALCnet) for TI-83/84+ (SE) calculators much easier.

### How to use it
At the moment gcntools only supports tokenization and detokenization of strings through the use of *TokenTools*

    t = TokenTools()

Upon instantiation, TokenTools dumps the tokens from the TI calculator's character sets into two dictionaries. These are:

    t.tokens
    t.two_byte_tokens

If you want to detokenize a string, you call the *detokenize()* method:

    t.detokenize(byte_string)

If you want to tokenize a string, so your calculator can understand it, call the *tokenize()* method:

    t.tokenize(string)

### License
This code is licensed under the BSD three clause license. See LICENSE for more information
