import pytz
from datetime import datetime
import os
from ftplib import FTP
from fastapi import FastAPI, HTTPException, Query, Request
from starlette.responses import JSONResponse
from tempfile import NamedTemporaryFile
import subprocess
import requests
from typing import Optional, List
from PIL import Image, ImageOps, ImageDraw, ImageFont
from io import BytesIO
import httpx


def log_to_ftp(ftp_host: str, ftp_username: str, ftp_password: str, log_message: str, log_folder: str = "logs"):
    """
    Enregistre un message de log dans un dossier spécifié sur un serveur FTP.

    Args:
    - ftp_host (str): L'hôte du serveur FTP.
    - ftp_username (str): Le nom d'utilisateur pour se connecter au serveur FTP.
    - ftp_password (str): Le mot de passe pour se connecter au serveur FTP.
    - log_message (str): Le message à enregistrer dans le fichier de log.
    - log_folder (str): Le dossier sur le serveur FTP où le fichier de log sera enregistré.
    """

    # Crée un nom de fichier basé sur la date et l'heure actuelle
    tz = pytz.timezone('Europe/Paris')

    now = datetime.now(tz)

    log_filename = f"log_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    log_file_path = os.path.join(log_folder, log_filename).replace('\\', '/')
    
    print(f"Tentative de log FTP dans : {log_file_path}")  # Débogage
    
    with NamedTemporaryFile("w", delete=False) as temp_log_file:
        temp_log_file.write(log_message)
        temp_log_path = temp_log_file.name

    try:
        with FTP(ftp_host, ftp_username, ftp_password) as ftp:
            ftp.cwd('/')  # Assurez-vous d'être à la racine
            if log_folder != '/':  # Vérifie si le dossier de logs n'est pas la racine
                ensure_ftp_path(ftp, log_folder)
            with open(temp_log_path, 'rb') as file:
                ftp.storbinary(f'STOR {log_file_path}', file)
    except Exception as e:
        print(f"Erreur lors du téléversement du log sur FTP : {e}")
    finally:
        os.remove(temp_log_path)  # Nettoyage du fichier temporaire



def ensure_ftp_path(ftp, path):
    """Crée récursivement le chemin sur le serveur FTP si nécessaire."""
    path = path.lstrip('/')  # Supprime le slash initial pour éviter les chemins absolus
    directories = path.split('/')
    
    current_path = ''
    for directory in directories:
        if directory:  # Ignore les chaînes vides
            current_path += "/" + directory
            try:
                ftp.cwd(current_path)  # Tente de naviguer dans le dossier
            except Exception:
                ftp.mkd(current_path)  # Crée le dossier s'il n'existe pas
                ftp.cwd(current_path)  # Navigue dans le dossier nouvellement créé



def clean_up_files(file_paths: list):
    """Supprime les fichiers temporaires spécifiés."""
    for path in file_paths:
        if path and os.path.exists(path):
            os.remove(path)

def upload_file_ftp(file_path: str, ftp_host: str, ftp_username: str, ftp_password: str, output_path: str):
    """
    Téléverse un fichier sur un serveur FTP.

    Args:
    - file_path (str): Le chemin local du fichier à téléverser.
    - ftp_host (str): L'hôte du serveur FTP.
    - ftp_username (str): Le nom d'utilisateur pour se connecter au serveur FTP.
    - ftp_password (str): Le mot de passe pour se connecter au serveur FTP.
    - output_path (str): Le chemin complet sur le serveur FTP où le fichier doit être téléversé.

    Cette fonction assure que le chemin de destination existe sur le serveur FTP
    et téléverse le fichier spécifié à cet emplacement.
    """
    with FTP(ftp_host, ftp_username, ftp_password) as ftp:
        # Assure que le chemin du dossier existe sur le serveur FTP
        directory_path, filename = os.path.split(output_path)
        ensure_ftp_path(ftp, directory_path)
        
        # Construit le chemin complet du fichier sur le serveur FTP
        ftp.cwd('/')  # S'assure de partir de la racine
        complete_path = os.path.join(directory_path, filename).lstrip('/')
        
        # Téléverse le fichier
        with open(file_path, 'rb') as file:
            ftp.storbinary(f'STOR {complete_path}', file)


# async def fetch_image(url):
#     async with httpx.AsyncClient() as client:
#         resp = await client.get(url)
#     return Image.open(BytesIO(resp.content))

def load_image(image_url: str) -> Image:
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    return img

def apply_rotation(img: Image, rotation: int) -> Image:
    return img.rotate(rotation, expand=True, fillcolor=None)

def apply_crop(img: Image, dh: int, db: int) -> Image:
    width, height = img.size
    top = (dh / 100) * height
    bottom = height - (db / 100) * height
    return img.crop((0, top, width, bottom))

def apply_filter(img: Image, filter: str) -> Image:
    if filter == 'NB':
        return ImageOps.grayscale(img)
    elif filter == 'SE':
        return ImageOps.sepia(img)
    else:
        return img

def add_text(
    img: Image = Image.new('RGB', (100, 100)), 
    text: str = "Sample Text", 
    font_name: str = "arial", 
    font_size: int = 20, 
    x: int = 10, 
    y: int = 10, 
    align: Optional[str] = "left"
) -> Image:
    from PIL import ImageDraw, ImageFont

    if isinstance(font_name, list):
        font_name = font_name[0]  # or some other logic to select the correct item

    if isinstance(font_size, list):
        font_size = font_size[0]  # or some other logic to select the correct item

    font = ImageFont.truetype(font_name, font_size)
    draw = ImageDraw.Draw(img)
    draw.text((x, y), text, font=font, align=align)

    return img


def process_and_upload(template_url, image_url, result_file, xs, ys, rs, ws, cs, dhs, dbs, ts, tfs, tts, txs, tys, tas, ftp_host, ftp_username, ftp_password):
    """
    A function to download data, process it, and upload it to a server.
    """
    try:
        template = load_image(template_url)
        image = load_image(image_url)

        for i, _ in enumerate(xs):
            try:
                rotation = rs[i] if i < len(rs) else 0
                image = apply_rotation(image, rotation)
                
                top = dhs[i] if i < len(dhs) else 0
                bottom = dbs[i] if i < len(dbs) else 0
                image = apply_crop(image, top, bottom)
                
                filter_ = cs[i] if i < len(cs) else None
                image = apply_filter(image, filter_)
                
                new_width = int((ws[i] / 100) * image.width) if i < len(ws) else image.width
                new_height = int(new_width * image.height / image.width)
                image = image.resize((new_width, new_height))
                
                x = int(xs[i] / 100 * template.width) if i < len(xs) else 0
                y = int(template.height - (ys[i] / 100 * template.height) - image.height) if i < len(ys) else 0
                template.paste(image, (x, y))
                
            except ValueError as e:
                log_message = f"Error at step {i}: {e}"
                log_to_ftp(
                    ftp_host=ftp_host,
                    ftp_username=ftp_username,
                    ftp_password=ftp_password,
                    log_message=log_message,
                    log_folder="/log_folder")

        if result_file:
            template.save(result_file)
            upload_file_ftp(result_file, ftp_host, ftp_username, ftp_password, result_file)
    
    except Exception as e:
        log_message = f"General error during processing: {str(e)}"
        print(log_message)
        log_to_ftp(
                    ftp_host=ftp_host,
                    ftp_username=ftp_username,
                    ftp_password=ftp_password,
                    log_message=log_message,
                    log_folder="/log_folder")
    
    finally:
        clean_up_files([result_file])