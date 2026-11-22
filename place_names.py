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


def place_name(identifier):
    return PLACE_NAMES.get(identifier, identifier)


def localize_place_names(text):
    for identifier in sorted(PLACE_NAMES, key=len, reverse=True):
        text = text.replace(identifier, PLACE_NAMES[identifier])
    return text
