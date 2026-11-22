"""English business labels for stable building identifiers stored in existing saves."""

PLACE_NAMES = {
    "Foundry Casino": "Lisbon Casino",
    "Pastéis de Belém": "Belem Pastry Shop",
    "Estaleiro do Tejo": "Tagus Shipyard",
    "Mercado das Nações": "Nations Market",
    "Quinta de Palmela": "Palmela Farm",
    "Armazém do Seixal": "Seixal Warehouse",
    "Bolsa de Lisboa": "Lisbon Stock Exchange",
}

DISPLAY_TERMS = {
    "Portagem": "Toll",
    "portagem": "toll",
    "Lisboa": "Lisbon",
    "Tejo": "Tagus",
    "Pastéis": "Pastries",
    "pastéis": "pastries",
}


def place_name(identifier):
    return PLACE_NAMES.get(identifier, identifier)


def localize_place_names(text):
    for identifier in sorted(PLACE_NAMES, key=len, reverse=True):
        text = text.replace(identifier, PLACE_NAMES[identifier])
    for source, english in DISPLAY_TERMS.items():
        text = text.replace(source, english)
    return text
