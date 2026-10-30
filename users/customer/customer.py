from flask import Blueprint, flash, redirect, render_template, session, url_for

from users.models import PrintShop

customer_bp = Blueprint('customer_bp', __name__, template_folder='templates', static_folder='static', static_url_path='/users/customer/static')


@customer_bp.route('/')
def index():
    return render_template('index.html')


@customer_bp.route('/printshops')
def printshops():
    # Require a signed-in account before allowing access to the directory.
    if 'user_id' not in session:
        flash('Please log in to browse printshops.', 'error')
        return redirect(url_for('auth.login'))

    # Fetch printshops in name order for the directory.
    printshops = PrintShop.query.order_by(PrintShop.name.asc()).all()

    # Prepare each shop's active services and products for the details modal.
    shop_cards = []
    for shop in printshops:
        services = [
            {
                'name': service.name,
                'category': service.category,
                'description': service.description,
            }
            for service in sorted(shop.offerings, key=lambda item: item.name.lower())
            if service.is_active
        ]
        shop_cards.append({'shop': shop, 'services': services})

    return render_template('printshops.html', shop_cards=shop_cards)
