import base64
import binascii
import json
import os
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt
from Crypto.Random import get_random_bytes

class ConfigurationManager:
    def __init__(self, plugin, logger):
        """
        Initializes a new instance of the ConfigurationManager class.

        Parameters:
            plugin (object): The plugin instance associated with this configuration manager.
            logger (object): The logger instance used for logging events and errors.

        Returns:
            None
        """
        self.logger = logger
        self.plugin = plugin
        self.key_file_path = None
        self.salt_file_path = None
        self.config_file_path = None
        self.config_folder_path = None

    def _create_config_file(self):
        """
        The `_create_config_file` function creates a configuration file with default settings if it does
        not already exist.
        """
        self.config_folder_path = self.plugin.get_plugin_data_folder()
        self.config_file_path = os.path.join(self.config_folder_path, "config.json")

        if not os.path.exists(self.config_folder_path):
            os.makedirs(self.config_folder_path)
        if not os.path.exists(self.config_file_path):
            default_config = self.get_default_config()
            try:
                with open(self.config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4)
            except Exception as e:
                self.logger.error(f"Error creating configuration file: {e}")
            
    def get_default_config(self):
        """
        The function `get_default_config` returns a default configuration dictionary with preset values
        for database connection, printer ID, currency symbol, and electricity cost.
        :return: A dictionary containing default configuration settings for a system or application. The
        dictionary includes keys such as "db_user", "db_password", "db_host", "db_port", "db_database",
        "printer_id", "currency", and "electricity_cost" with corresponding default values.
        """
        return {
            "db_user": "user",
            "db_password": "password",
            "db_host": "host",
            "db_port": "3306",
            "db_database": "database",
            "printer_id": 0,
            "currency": "\u20ac",
            "electricity_cost": 0.0
        }

    def _initialize_config_files(self):
        """
        The function `_initialize_config_files` initializes key, salt, and creates a configuration file.
        """
        self._initialize_key_and_salt()
        self._create_config_file()

    def _load_existing_config(self):
        """
        The function `_load_existing_config` reads and returns a JSON configuration file, logging an error
        if there is an issue.
        :return: The method `_load_existing_config` is returning the loaded JSON data from the configuration
        file if the file is successfully opened and read. If an exception occurs during the process (such as
        file not found or invalid JSON format), it logs an error message using the logger and returns
        `None`.
        """
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            return None
            
    def _update_config(self, data):
        """
        Updates the existing configuration with the provided data.
        :param data: A dictionary containing the updated configuration settings.
        :return: None
        """
        updated_settings = self._load_existing_config()
        updated_settings.update(data)

        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(updated_settings, f, indent=4)
            self.logger.info("Configuration updated successfully.")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")

    def _initialize_key_and_salt(self):
        """
        Initializes the encryption key and salt for the plugin.

        This function checks if the encryption key and salt files exist in the plugin's data folder. If they do not exist,
        it generates a new encryption key and salt, saves them to the respective files, and logs the successful
        generation. If the files already exist, it reads the encryption key and salt from the files.
        Parameters:
            self (ConfigurationManager): The instance of the ConfigurationManager class.
        Returns:
            None
        Raises:
            Exception: If there is an error generating or loading the encryption key and salt.

        """
        self.key_file_path = os.path.join(self.plugin.get_plugin_data_folder(), 'key.key')
        self.salt_file_path = os.path.join(self.plugin.get_plugin_data_folder(), 'salt.key')

        if not (os.path.exists(self.key_file_path) and os.path.exists(self.salt_file_path)):
            self.salt = get_random_bytes(16)
            self.key = scrypt(b'some_password', self.salt, 32, N=2**14, r=8, p=1)
            try:
                with open(self.key_file_path, 'wb') as key_file:
                    key_file.write(self.key)
                with open(self.salt_file_path, 'wb') as salt_file:
                    salt_file.write(self.salt)
                self.logger.info("Generated and saved new encryption key and salt")
            except Exception as e:
                self.logger.error(f"Error generating key and salt: {e}")
        else:
            try:
                with open(self.key_file_path, 'rb') as key_file:
                    self.key = key_file.read()
                with open(self.salt_file_path, 'rb') as salt_file:
                    self.salt = salt_file.read()
            except Exception as e:
                self.logger.error(f"Error loading key and salt: {e}")

    def _encrypt(self, password):
        """
        Encrypts a given password using AES encryption with EAX mode.

        Parameters:
            password (str): The password to be encrypted.

        Returns:
            str: The encrypted password as a base64 encoded string.
        """
        cipher = AES.new(self.key, AES.MODE_EAX)
        ciphertext, tag = cipher.encrypt_and_digest(password.encode())
        return base64.b64encode(cipher.nonce + tag + ciphertext).decode()

    def _decrypt(self, encrypted_password):
        """
        Decrypts an encrypted password using AES encryption with EAX mode.

        Args:
            encrypted_password (str): The encrypted password to be decrypted.

        Returns:
            str: The decrypted password as a string.

        Raises:
            ValueError: If the encrypted password is not a valid base64 encoded string.
            KeyError: If the decryption key is not valid.
            binascii.Error: If the ciphertext is not valid.

        """
        try:
            data = base64.b64decode(encrypted_password)
            nonce, tag, ciphertext = data[:16], data[16:32], data[32:]
            cipher = AES.new(self.key, AES.MODE_EAX, nonce=nonce)
            return cipher.decrypt_and_verify(ciphertext, tag).decode()
        except (ValueError, KeyError, binascii.Error) as e:
            self.logger.error(f"Decryption failed: {e}")
            return None
