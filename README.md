# Chrome Cookie Decryptor

A Python script that retrieves and decrypts cookies from all Chrome profiles using both old and latest decryption methods. This tool is useful for developers and security researchers who need to analyze cookie data.

## Features

- Decrypts cookies stored in Chrome's SQLite database.
- Supports both v10 and v20 cookie formats.
- Automatically retrieves the necessary encryption keys from Chrome's Local State.
- Outputs decrypted cookies to text files for each profile.

## Requirements

- Python 3.x
- Required Python packages:
  - `pycryptodome`
  - `pypsexec`
  - `pyaes`
  - `pywin32`

You can install the required packages using pip:

```bash
pip install pycryptodome pypsexec pyaes pywin32
```

1. Usage:

Download One of the releases : 

OR

Clone the repository:

```bash
git clone https://github.com/yourusername/chrome-cookie-decryptor.git
cd chrome-cookie-decryptor
```

Run the script:

```bash
python chrome_cookie_decryptor.py
```
Output:

The script will generate a text file for each Chrome profile in the current directory, containing the decrypted cookies in a tab-separated format.

2. How It Works:

Profile Path Retrieval: The script retrieves the path to the user's Chrome profiles from the environment variable.

Key Extraction: It loads the Local State JSON file to access the encryption keys used by Chrome.

Cookie Decryption: The script uses the appropriate decryption methods based on the cookie version:

For v10 and v11 cookies, it uses AES GCM mode.
For v20 cookies, it retrieves the decryption key using Windows DPAPI and then decrypts the cookies.
Output Generation: Decrypted cookies are written to text files named after each profile.

Disclaimer

This tool is intended for educational and research purposes only. Misuse of this tool can lead to legal consequences. Always ensure you have permission to access and analyze the data you are working with.

Contributing

If you'd like to contribute to this project, feel free to fork the repository and submit a pull request. Any contributions, suggestions, or improvements are welcome!

License
This project is licensed under the MIT License. See the LICENSE file for details.

Acknowledgments
pycryptodome
pypsexec
pyaes
