from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from Crypto.Hash import SHA256
from pathlib import Path
from typing import Optional
import os
import structlog

log = structlog.get_logger()

class AES256Crypto:
    """AES-256-GCM encryption with PBKDF2 key derivation."""
    
    SALT_SIZE = 16
    IV_SIZE = 12  # GCM IV
    TAG_SIZE = 16
    KEY_SIZE = 32  # 256 bits
    ITERATIONS = 100_000  # PBKDF2
    CHUNK_SIZE = 8192
    
    async def encrypt_file(
        self,
        file_path: str,
        password: str,
        output_path: Optional[str] = None
    ) -> str:
        """Encrypt file with AES-256-GCM."""
        
        input_file = Path(file_path)
        if not input_file.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not output_path:
            output_path = str(input_file.with_suffix(input_file.suffix + ".enc"))
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Generate salt & derive key
            salt = get_random_bytes(self.SALT_SIZE)
            key = PBKDF2(
                password,
                salt,
                dkLen=self.KEY_SIZE,
                count=self.ITERATIONS,
                hmac_hash_module=SHA256
            )
            
            # Create cipher
            cipher = AES.new(key, AES.MODE_GCM)
            iv = cipher.nonce  # GCM generates nonce
            
            # Write: salt + IV + encrypted_data + tag
            with open(input_file, 'rb') as infile, open(output_file, 'wb') as outfile:
                outfile.write(salt)
                outfile.write(iv)
                
                # Encrypt in chunks
                while chunk := infile.read(self.CHUNK_SIZE):
                    ciphertext = cipher.encrypt(chunk)
                    outfile.write(ciphertext)
                
                # Append auth tag
                tag = cipher.digest()
                outfile.write(tag)
            
            log.info(
                "file_encrypted",
                input=str(input_file),
                output=str(output_file),
                size_bytes=input_file.stat().st_size
            )
            
            return str(output_file)
        
        except Exception as e:
            if output_file.exists():
                output_file.unlink()
            raise
    
    async def decrypt_file(
        self,
        encrypted_path: str,
        password: str,
        output_path: Optional[str] = None
    ) -> str:
        """Decrypt AES-256-GCM file."""
        
        encrypted_file = Path(encrypted_path)
        if not encrypted_file.exists():
            raise FileNotFoundError(f"File not found: {encrypted_path}")
        
        if not output_path:
            output_path = str(encrypted_file.with_suffix(''))
        
        output_file = Path(output_path)
        
        try:
            with open(encrypted_file, 'rb') as f:
                salt = f.read(self.SALT_SIZE)
                iv = f.read(self.IV_SIZE)
                
                # Derive key
                key = PBKDF2(
                    password, 
                    salt, 
                    dkLen=self.KEY_SIZE, 
                    count=self.ITERATIONS,
                    hmac_hash_module=SHA256
                )
                
                # Create cipher
                cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                
                # Read & decrypt
                ciphertext = f.read()[:-self.TAG_SIZE]  # Exclude tag
                # Read auth tag from the end
                f.seek(-self.TAG_SIZE, os.SEEK_END)
                tag = f.read(self.TAG_SIZE)
                
                plaintext = cipher.decrypt(ciphertext)
                cipher.verify(tag)  # Raises ValueError if auth fails
            
            with open(output_file, 'wb') as f:
                f.write(plaintext)
            
            log.info("file_decrypted", input=str(encrypted_file), output=str(output_file))
            return str(output_file)
        
        except ValueError as e:
            log.error("decrypt_auth_fail", error=str(e))
            raise Exception("Decryption failed: invalid password or corrupted file")
