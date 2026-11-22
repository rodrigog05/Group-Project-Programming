"""Portuguese labels for stable building identifiers stored in existing saves."""

PLACE_NAMES = {
    "Iron Hill Mine": "Armazém de Minérios",
    "Ironworks": "Oficina do Ferro",
    "Tool Market": "Loja de Ferragens",
    "Pine Mill": "Madeireira dos Pinheiros",
    "Oak Workshop": "Carpintaria do Carvalho",
    "Home Market": "Casa dos Móveis",
    "Redbank Clay Pit": "Depósito de Argila",
    "Ember Kiln": "Forno de Cerâmica",
    "The Pottery Shop": "Loja de Olaria",
    "Goldenfield Farm": "Armazém de Cereais",
    "Sunrise Bakery": "Padaria do Sol",
    "Daily Bread Market": "Pão de Cada Dia",
    "Foundry Casino": "Casino de Lisboa",
    "Motorworks Garage": "Garagem Central",
    "Foundry Warehouse": "Armazém Central",
    "Oriente Tool Market": "Ferragens do Oriente",
    "Quinta de Palmela": "Quinta de Palmela",
    "Cacilhas Dealership": "Concessionário de Cacilhas",
    "Foundry Precision Works": "Oficina de Precisão",
}


def place_name(identifier):
    return PLACE_NAMES.get(identifier, identifier)


def localize_place_names(text):
    # Longest first: Oriente Tool Market must be replaced before Tool Market.
    for identifier in sorted(PLACE_NAMES, key=len, reverse=True):
        text = text.replace(identifier, PLACE_NAMES[identifier])
    return text
