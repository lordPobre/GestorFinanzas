from io import BytesIO

from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile

LADO_MAXIMO = 1024
PIXELES_MAXIMOS = 40_000_000
FORMATOS = {'JPEG', 'MPO', 'PNG', 'WEBP', 'GIF'}
CALIDAD = 85


def recodificar(archivo):
    from PIL import Image, ImageOps, UnidentifiedImageError

    error = forms.ValidationError('No pudimos leer esa imagen. Prueba con una foto JPG o PNG.')
    try:
        archivo.seek(0)
        with Image.open(archivo) as original:
            if original.format not in FORMATOS:
                raise error
            if original.width * original.height > PIXELES_MAXIMOS:
                raise forms.ValidationError('La imagen tiene demasiados píxeles.')
            original.load()
            imagen = ImageOps.exif_transpose(original)
            if imagen.mode in ('RGBA', 'LA', 'P'):
                imagen = imagen.convert('RGBA')
                fondo = Image.new('RGB', imagen.size, (255, 255, 255))
                fondo.paste(imagen, mask=imagen.getchannel('A'))
                imagen = fondo
            elif imagen.mode != 'RGB':
                imagen = imagen.convert('RGB')
            imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
            salida = BytesIO()
            imagen.save(salida, 'JPEG', quality=CALIDAD, optimize=True)
    except forms.ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as e:
        raise error from e
    return SimpleUploadedFile('foto.jpg', salida.getvalue(), content_type='image/jpeg')
