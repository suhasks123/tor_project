import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.backends.openssl import backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from typing import Any
import json

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from cell.control_cell import TapCHData
from cryptography.hazmat.primitives.asymmetric import padding
#from cryptography.hazmat.primitives import hashes

class CryptoConstants:
    KEY_LEN = 16  # The length of the stream cipher's key, in bytes
    DH_LEN = 128  # The number of bytes used to represent a member of Diffie Hellman group
    DH_SEC_LEN = 40  # The number of bytes used in a Diffie-Hellman private key (x)
    PK_ENC_LEN = 128  # The length of a public-key encrypted message, in bytes.
    PK_PAD_LEN = 42  # The number of bytes added in padding for public-key
    # encryption, in bytes. (The largest number of bytes that can be encrypted
    # in a single public-key operation is therefore PK_ENC_LEN-PK_PAD_LEN.)
    HASH_LEN = 20   # The length of the hash function's output, in bytes


class CoreCryptoRSA:
    """
    This is the RSA core crypto module for the entire project. It behaves as a wrapper crypto primitives
    """

    # Constants used in the Tor Spec for RSA
    RSA_FIXED_EXPONENT = 65537
    RSA_KEY_SIZE = 1024

    @staticmethod
    def generate_rsa_key_pair() -> (rsa.RSAPrivateKey, rsa.RSAPublicKey):
        """
        The function generates a new RSA key pair to be used
        :returns a 2-tuple of type -> (rsa.RSAPrivateKey, rsa.RSAPublicKey)
        """

        private_key = rsa.generate_private_key(
            public_exponent=CoreCryptoRSA.RSA_FIXED_EXPONENT,
            key_size=CoreCryptoRSA.RSA_KEY_SIZE,
            backend=default_backend()
        )
        public_key = private_key.public_key()

        return private_key, public_key

    @staticmethod
    def load_private_key_from_disc(pem_file: str, password_for_encryption=None) -> rsa.RSAPrivateKey:

        """
        Loads a pem file into a RSAPrivateKey Object.
        :param password_for_encryption: The password that might have been used for encrypting the pem file itself
        :param pem_file: The file containing the private RSA key
        :return: RSAPrivateKey object
        """
        try:
            with open(pem_file, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=password_for_encryption,
                    backend=default_backend()
                )
                return private_key
        except:
            print("Error reading the pem file.")
            return None

    @staticmethod
    def load_public_key_from_disc(pem_file: str) -> rsa.RSAPublicKey:
        """
        Loads a pem file into a RSAPublicKey Object.
        :param pem_file: The file containing the public RSA key
        :return: RSAPublicKey Object.
        """

        try:
            with open(pem_file, "rb") as key_file:
                public_key = serialization.load_ssh_public_key(
                    key_file.read(),
                    backend=default_backend()
                )
                return public_key
        except:
            print("Error reading the pem file.")
            return None

    @staticmethod
    def load_key_pair_from_disc(pem_file: str, password_for_pem_file=None) -> (rsa.RSAPrivateKey, rsa.RSAPublicKey):
        """
        This function simply takes the private key pem file and gives you back the entire key pair
        :param pem_file: The file containing the private RSA key
        :param password_for_pem_file: The password that might have been used for encrypting the pem file itself
        :return: a 2-tuple of type -> (rsa.RSAPrivateKey, rsa.RSAPublicKey)
        """

        private_key = CoreCryptoRSA.load_private_key_from_disc(pem_file, password_for_pem_file)
        public_key = private_key.public_key()

        return private_key, public_key

    @staticmethod
    def hybrid_encrypt(message: str, pk: rsa.RSAPublicKey) -> Any:
        """
        This method is the hybrid encrypt outlined in the Tor spec 0.4 section
        :param message: The message to be encrypted
        :param pk: The RSA public to encrypt the message with
        :return: The encrypted message (json string)
        """
        if len(message)<=CryptoConstants.PK_ENC_LEN-CryptoConstants.PK_PAD_LEN:
            p = pk.encrypt(message,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
            jsonstr=TapCHData(str(pk),None,p,None)
        else:
            k = os.urandom(CryptoConstants.KEY_LEN)
            m1=message[0:CryptoConstants.PK_ENC_LEN-CryptoConstants.PK_PAD_LEN-CryptoConstants.KEY_LEN]
            m2=message[CryptoConstants.PK_ENC_LEN-CryptoConstants.PK_PAD_LEN-CryptoConstants.KEY_LEN:]
            p1 = pk.encrypt(bytes(k.decode('utf-8')+m1),padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))


            backend = default_backend()
            nonce = bytearray(len(m2))#all bytes are 0, nonce is the IV
            cipher = Cipher(algorithms.AES(k), modes.CTR(nonce), backend=backend)
            encryptor = cipher.encryptor()
            p2 = encryptor.update(bytes(m2, encoding='utf-8')) + encryptor.finalize()

            jsonstr=TapCHData(nonce.decode('utf-8'),k.decode('utf-8'),p1,p2)

        # convert into JSON:
        y = jsonstr.net_serialize()

        # the result is a JSON string:
        return y


    @staticmethod
    def hybrid_decrypt(message: str, pk: rsa.RSAPrivateKey) -> str:
        """
        This method is the hybrid decrypt outlined in the Tor spec 0.4 section
        :param message: The message to be decrypted
        :param pk: The RSA private key to decrypt the message with
        :return: The decrypted message (json string)
        """

        json_inp=TapCHData.net_deserialize(message)
        x=json_inp.serialize()
        #x is now a dictionary

        if x["SYMKEY"]==None:
            return_message = pk.decrypt(x["GX1"],padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
        else:
            km1 = pk.decrypt(x["GX1"],padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
            m1=km1[len(x["SYMKEY"]):]

            backend = default_backend()
            cipher = Cipher(algorithms.AES(x["SYMKEY"]), modes.CTR(x["PADDING"]), backend=backend)
            decryptor = cipher.decryptor()
            m2=decryptor.update(x["GX2"]) + decryptor.finalize()

            return_message=m1+m2

        return return_message

    @staticmethod
    def kdf_tor(message: str) -> dict:
      """
      This method is the key derivative outlined in the Tor spec section 5.2.1
      :param message: The message to be used to carry out KDF
      :return: The output
      """
      backend = default_backend()
      hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_LEN*2+HASH_LEN*3,
        salt=None,
        info=None,
        backend=backend
      )

      key = hkdf.derive(message.encode())

      kdf_tor_dict = {
        'KH': key[:HASH_LEN],
        'Df': key[HASH_LEN:(2*HASH_LEN)],
        'Db': key[(2*HASH_LEN):(3*HASH_LEN)],
        'Kf': key[(3*HASH_LEN):((3*HASH_LEN)+KEY_LEN)],
        'Kb': key[((3*HASH_LEN)+KEY_LEN):((3*HASH_LEN)+(2*KEY_LEN))]
      }

      # As of now, the function returns a dictionary due to certain problems with
      # converting byte object to python strings. This needs to be fixed in the future

      return kdf_tor_dict
    

class CoreCryptoDH:

    @staticmethod
    def generate_dh_priv_key() -> (str, str):
        return "x", "g^x"

    @staticmethod
    def compute_dh_shared_key(gy: str, x: str) -> str:
        return "gxy"

class CoreCryptoMisc:

    @staticmethod
    def calculate_digest(message_dict):
        digest_obj = hashes.Hash(hashes.SHA256(), backend=default_backend())
        for data in message_dict.values():
            str_data = str(data)
            digest_obj.update(str_data.encode())
        digest = digest_obj.finalize()
        return digest