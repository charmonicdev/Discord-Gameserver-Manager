# encryption_manager.py
# Handles encryption and decryption of sensitive data with obfuscation

import os
import base64
import hashlib
import json
from cryptography.fernet import Fernet
from constants import KEY_FILE, KEY_BACKUP_FILE, KEY_METADATA_FILE


class EncryptionManager:
    def __init__(self):
        self.cipher = None
        self.master_key = None
        self.load_or_create_obfuscated_key()
    
    def _obfuscate_key(self, raw_key):
        """Apply multiple transformations to obfuscate the key."""
        # First, reverse the key
        reversed_key = raw_key[::-1]
        
        # Apply additional XOR with a fixed pattern
        pattern = b'\xDE\xAD\xBE\xEF\xCA\xFE\xBA\xBE'  # Hex pattern for additional obscurity
        pattern_extended = pattern * (len(reversed_key) // len(pattern) + 1)
        xored = bytes(a ^ b for a, b in zip(reversed_key, pattern_extended[:len(reversed_key)]))
        
        # Add a random-looking header
        header = b'\x00\xFF\x00\xFF'  # Looks like binary data marker
        
        return header + xored
    
    def _deobfuscate_key(self, obfuscated_key):
        """Reverse the obfuscation to get the original key."""
        # Remove the header
        if obfuscated_key[:4] == b'\x00\xFF\x00\xFF':
            obfuscated_key = obfuscated_key[4:]
        
        # Reverse the XOR operation
        pattern = b'\xDE\xAD\xBE\xEF\xCA\xFE\xBA\xBE'
        pattern_extended = pattern * (len(obfuscated_key) // len(pattern) + 1)
        xored = bytes(a ^ b for a, b in zip(obfuscated_key, pattern_extended[:len(obfuscated_key)]))
        
        # Reverse the string
        return xored[::-1]
    
    def _generate_machine_fingerprint(self):
        """Generate a machine-specific fingerprint for additional security."""
        import platform
        import getpass
        
        # Combine various system identifiers
        system_info = f"{platform.node()}{platform.processor()}{getpass.getuser()}"
        return hashlib.sha256(system_info.encode()).digest()[:16]
    
    def _save_key_with_metadata(self, key_data):
        """Save key with misleading metadata."""
        try:
            # Create metadata that makes the file look like a real system file
            metadata = {
                "version": "2.0",
                "format": "binary",
                "compression": "none",
                "created": str(os.path.getctime(__file__)) if os.path.exists(__file__) else "0",
                "machine_fingerprint": base64.b64encode(self._generate_machine_fingerprint()).decode(),
                "checksum": hashlib.sha256(key_data).hexdigest()[:16]
            }
            
            # Store both key and metadata in the backup file
            with open(KEY_BACKUP_FILE, 'wb') as f:
                # Write a fake header that looks like a different file type
                fake_header = b'PK\x03\x04'  # ZIP file header
                f.write(fake_header)
                # Write the actual data
                f.write(key_data)
            
            # Store metadata separately
            with open(KEY_METADATA_FILE, 'w') as f:
                json.dump(metadata, f)
            
            # Store the main obfuscated key
            with open(KEY_FILE, 'wb') as f:
                f.write(key_data)
                
        except Exception as e:
            print(f"Error saving key with metadata: {e}")
    
    def _load_key_with_metadata(self):
        """Load key from obfuscated storage."""
        # Try main key file first
        if os.path.exists(KEY_FILE):
            try:
                with open(KEY_FILE, 'rb') as f:
                    return f.read()
            except Exception:
                pass
        
        # Try backup if main file fails
        if os.path.exists(KEY_BACKUP_FILE):
            try:
                with open(KEY_BACKUP_FILE, 'rb') as f:
                    f.read(4)  # Skip fake ZIP header
                    return f.read()
            except Exception:
                pass
        
        return None
    
    def load_or_create_obfuscated_key(self):
        """Load existing obfuscated key or create a new one."""
        key_data = self._load_key_with_metadata()
        
        if key_data:
            try:
                # Deobfuscate the key
                deobfuscated = self._deobfuscate_key(key_data)
                # The deobfuscated data is the actual Fernet key
                self.cipher = Fernet(deobfuscated)
                print("Encryption key loaded from obfuscated storage")
            except Exception as e:
                print(f"Error loading obfuscated key: {e}")
                self.create_new_obfuscated_key()
        else:
            self.create_new_obfuscated_key()
    
    def create_new_obfuscated_key(self):
        """Create a new obfuscated encryption key."""
        try:
            # Generate a standard Fernet key
            raw_key = Fernet.generate_key()
            
            # Obfuscate the key
            obfuscated_key = self._obfuscate_key(raw_key)
            
            # Save with metadata
            self._save_key_with_metadata(obfuscated_key)
            
            # Initialize cipher with the raw key
            self.cipher = Fernet(raw_key)
            print("New obfuscated encryption key created and saved")
        except Exception as e:
            print(f"Error creating obfuscated key: {e}")
            raise
    
    def encrypt(self, data):
        """Encrypt a string."""
        if not data:
            return ""
        if not self.cipher:
            print("Encryption not available")
            return ""
        
        try:
            encrypted = self.cipher.encrypt(data.encode())
            # Double encode for additional obscurity in the config file
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            print(f"Encryption error: {e}")
            return ""
    
    def decrypt(self, encrypted_data):
        """Decrypt a string."""
        if not encrypted_data:
            return ""
        if not self.cipher:
            print("Decryption not available")
            return ""
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            print(f"Decryption error: {e}")
            return ""
    
    def is_key_available(self):
        """Check if encryption is available."""
        return self.cipher is not None
    
    def verify_key_integrity(self):
        """Verify that the key files are intact."""
        key_exists = os.path.exists(KEY_FILE)
        backup_exists = os.path.exists(KEY_BACKUP_FILE)
        metadata_exists = os.path.exists(KEY_METADATA_FILE)
        
        if key_exists and backup_exists and metadata_exists:
            return True
        elif backup_exists:  # Try to restore from backup
            try:
                with open(KEY_BACKUP_FILE, 'rb') as f:
                    f.read(4)  # Skip fake header
                    key_data = f.read()
                    with open(KEY_FILE, 'wb') as f2:
                        f2.write(key_data)
                print("Restored key from backup")
                return True
            except Exception:
                return False
        return False