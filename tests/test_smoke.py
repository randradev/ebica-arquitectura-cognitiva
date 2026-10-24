"""Prueba mínima: el paquete se instala y se importa."""

import ebica


def test_package_imports_with_version():
    """
    Verifica que el paquete `ebica` es importable y declara su versión.

    Confirma que la instalación editable (`pip install -e .`) funciona.
    """
    assert ebica.__version__ == "0.0.1"
