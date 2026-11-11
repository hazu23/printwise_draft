from datetime import time

from users import create_app, db
from users.models import PrintShop, PrintShopServices

SEED_PRINTSHOPS = [
    {
        "name": "Flexlab Printing Services",
        "description": "Prints you can flex.",
        "location": "107 Burzagom St. Bililan Sur, Pila, Laguna",
        "logo_path": "images/flexlab.png",
        "contact_phone": "0961 734 2318",
        "contact_email": "flexdotlab@gmail.com",
        "website": "https://www.facebook.com/flexlabprintingservices",
        "business_hours": None,
        "opening_time": None, "closing_time": None,
        "services": [
            {"name": "Signage", "category": "service", "description": None, "options": None},
            {"name": "Tarpaulin", "category": "service", "description": None, "options": None},
            {"name": "Stickers", "category": "service", "description": None, "options": None},
            {"name": "UV DTF", "category": "service", "description": None, "options": None},
            {"name": "Sintra", "category": "service", "description": None, "options": None},
            {"name": "T-shirts", "category": "service", "description": None, "options": None},
            {"name": "CO2 laser cutting", "category": "service", "description": None, "options": None},
            {"name": "Vehicle wrap/decals", "category": "service", "description": None, "options": None},
        ],
    },
    {
        "name": "On The Print",
        "description": "On The Print is available anytime and specializes in bulk orders.",
        "location": "Purok 4 Villa Sol 1 Labuin, Pila, Laguna",
        "logo_path": "images/OnThePrint.png",
        "contact_phone": None,
        "contact_email": "ontheprint2@gmail.com",
        "website": "https://www.facebook.com/profile.php?id=61550864192190",
        "business_hours": "Anytime",
        "opening_time": None, "closing_time": None,
        "services": [
            {
                "name": "Print",
                "category": "service",
                "description": None,
                "options": {
                    "description": "Document printing on bond paper. Price varies by paper size, color, and quantity.",
                    "fields": [
                        {"key": "paper_size", "label": "Paper size", "type": "text", "required": True, "placeholder": "Enter the paper size"},
                        {"key": "color", "label": "Print color", "type": "select", "required": True, "choices": ["Black and white", "Color"]},
                        {"key": "finish", "label": "Finish", "type": "text", "required": False, "placeholder": "Optional finishing request", "help": "Add a finish if the printshop offers it."},
                    ],
                },
            },
            {"name": "Scan", "category": "service", "description": None, "options": None},
            {"name": "Laminate", "category": "service", "description": None, "options": None},
            {"name": "Photo Develop", "category": "service", "description": None, "options": None},
            {"name": "Sticker labels", "category": "service", "description": None, "options": None},
            {"name": "Vinyl Sticker", "category": "service", "description": None, "options": None},
            {"name": "Invitations", "category": "service", "description": None, "options": None},
            {"name": "Calling Card", "category": "service", "description": None, "options": None},
            {"name": "Sintra Board", "category": "product", "description": None, "options": None},
            {"name": "Photo Frame", "category": "product", "description": None, "options": None},
            {"name": "Ref magnet", "category": "product", "description": None, "options": None},
            {"name": "Inspired Mini Polaroid", "category": "product", "description": None, "options": None},
            {"name": "Customized Acrylic keychain", "category": "product", "description": None, "options": None},
            {"name": "Photocopy/Xerox", "category": "service", "description": None, "options": None},
        ],
    },
    {
        "name": "Dan's Printing Services",
        "description": "Prints where you can see quality results.",
        "location": "310, Purok 3, Brgy. Pinagbayanan, Pila, Laguna",
        "logo_path": None,
        "contact_phone": None,
        "contact_email": "danhaidend@gmail.com",
        "website": "https://www.facebook.com/dan.haiden.dacuycuy.2025",
        "business_hours": "8:00 AM to 9:00 PM",
        "opening_time": time(8, 0), "closing_time": time(21, 0),
        "services": [
            {"name": "Document printing", "category": "service", "description": "Regular print on regular bondpaper.", "options": None},
            {"name": "Photocopy/Xerox", "category": "service", "description": None, "options": None},
            {"name": "Photo printing", "category": "service", "description": "Prints on photo paper.", "options": None},
            {"name": "Lamination", "category": "service", "description": None, "options": None},
            {"name": "ID picture", "category": "service", "description": "Prints on photo paper.", "options": None},
            {"name": "Sticker paper printing", "category": "service", "description": "Prints on sticker paper.", "options": None},
        ],
    },
]


def add_or_update_service(printshop, service_data):
    """Create one service, or update it when it already belongs to the shop."""
    service = PrintShopServices.query.filter_by(
        printshop_id=printshop.id,
        name=service_data["name"],
    ).first()

    if service is None:
        service = PrintShopServices(printshop_id=printshop.id, name=service_data["name"])
        db.session.add(service)

    service.category = service_data["category"]
    service.description = service_data["description"]
    service.options = service_data["options"]
    service.is_active = True


def add_or_update_printshop(shop_data):
    """Create one printshop, or update it when the name already exists."""
    printshop = PrintShop.query.filter_by(name=shop_data["name"]).first()

    if printshop is None:
        printshop = PrintShop(name=shop_data["name"], location=shop_data["location"])
        db.session.add(printshop)

    # Copy each basic printshop detail from the seed dictionary to the database row.
    printshop.description = shop_data["description"]
    printshop.location = shop_data["location"]
    printshop.logo_path = shop_data["logo_path"]
    printshop.contact_phone = shop_data["contact_phone"]
    printshop.contact_email = shop_data["contact_email"]
    printshop.website = shop_data["website"]
    printshop.business_hours = shop_data["business_hours"]
    printshop.opening_time = shop_data["opening_time"]
    printshop.closing_time = shop_data["closing_time"]

    # Flush gives a new printshop an ID before its services are created.
    db.session.flush()
    for service_data in shop_data["services"]:
        add_or_update_service(printshop, service_data)


def seed_printshops():
    """Add or update every printshop and service in SEED_PRINTSHOPS."""
    for shop_data in SEED_PRINTSHOPS:
        add_or_update_printshop(shop_data)

    db.session.commit()
    print("Printshops and services have been added or updated.")


if __name__ == "__main__":
    # create_app() connects Flask and SQLAlchemy before this script uses the models.
    app = create_app()
    with app.app_context():
        seed_printshops()
