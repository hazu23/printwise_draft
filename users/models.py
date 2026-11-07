from . import db

# main table.
class Account(db.Model):
    __tablename__ = "accounts"

    # Account identity and sign-in details. The password is stored as a hash.
    # Email must be unique for each account.
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # customer, staff, or admin

    # lets me jump from an account to its extra info. 
    # uselist=False means you get one item, not a list.
    customer = db.relationship("Customer", back_populates="account", uselist=False)
    staff = db.relationship("Staff", back_populates="account", uselist=False)
    admin = db.relationship("Admin", back_populates="account", uselist=False)


class Customer(db.Model):
    __tablename__ = "customers"

    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), primary_key=True
    )

    # gives the whole account row, so you dont have to look it up yourself.
    account = db.relationship("Account", back_populates="customer")


class Admin(db.Model):
    __tablename__ = "admin"

    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), primary_key=True
    )

    # Connect the admin record to its account and to printshops it manages.
    account = db.relationship("Account", back_populates="admin")
    printshops = db.relationship("PrintShop", back_populates="admin")


class PrintShop(db.Model):
    __tablename__ = "printshops"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(255), nullable=False)
    logo_path = db.Column(db.String(255), nullable=True)
    contact_phone = db.Column(db.String(30), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    business_hours = db.Column(db.String(255), nullable=True)

    admin_account_id = db.Column(
        db.Integer, db.ForeignKey("admin.account_id"), nullable=True
    )

    admin = db.relationship("Admin", back_populates="printshops")
    staff_members = db.relationship("Staff", back_populates="printshop")
    offerings = db.relationship("PrintShopServices", back_populates="printshop")


class PrintShopServices(db.Model):
    __tablename__ = "printshops_services"

    id = db.Column(db.Integer, primary_key=True)
    printshop_id = db.Column(
        db.Integer, db.ForeignKey("printshops.id"), nullable=False
    )
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(20), nullable=False, default="service")
    description = db.Column(db.Text, nullable=True)
    options = db.Column(db.JSON, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    printshop = db.relationship("PrintShop", back_populates="offerings")


class PrintRequest(db.Model):
    __tablename__ = "print_requests"

    id = db.Column(db.Integer, primary_key=True)
    customer_account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), nullable=False
    )
    printshop_id = db.Column(
        db.Integer, db.ForeignKey("printshops.id"), nullable=False
    )
    service_id = db.Column(
        db.Integer, db.ForeignKey("printshops_services.id"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False, default=1)
    selected_options = db.Column(db.JSON, nullable=False, default=dict)
    file_paths = db.Column(db.JSON, nullable=False, default=list)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    customer = db.relationship("Account")
    printshop = db.relationship("PrintShop")
    service = db.relationship("PrintShopServices")


class Staff(db.Model):
    # A staff row links an account to the printshop where that person works.
    __tablename__ = "staff"

    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), primary_key=True
    )
    printshop_id = db.Column(
        db.Integer, db.ForeignKey("printshops.id"), nullable=False
    )

    account = db.relationship("Account", back_populates="staff")
    printshop = db.relationship("PrintShop", back_populates="staff_members")
