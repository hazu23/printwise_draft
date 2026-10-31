from . import db

# Each class below describes a MySQL table. SQLAlchemy maps the class and its
# attributes to the table and columns so the rest of the app can use Python.
class Account(db.Model):
    __tablename__ = "accounts"

    # Account identity and sign-in details. The password is stored as a hash,
    # not as the original password. Email must be unique for each account.
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # customer, staff, or admin

    # Connect this account to its role-specific record. uselist=False means
    # each account has at most one matching customer, staff, or admin record.
    customer = db.relationship("Customer", back_populates="account", uselist=False)
    staff = db.relationship("Staff", back_populates="account", uselist=False)
    admin = db.relationship("Admin", back_populates="account", uselist=False)


class Customer(db.Model):
    __tablename__ = "customers"

    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), primary_key=True
    )

    # Let Python code move from a customer record to its Account object.
    account = db.relationship("Account", back_populates="customer")


class Admin(db.Model):
    # Store admin-specific information separately while reusing the account ID.
    __tablename__ = "admin"

    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), primary_key=True
    )

    # Connect the admin record to its account and to printshops it manages.
    account = db.relationship("Account", back_populates="admin")
    printshops = db.relationship("PrintShop", back_populates="admin")


class PrintShop(db.Model):
    # Each row represents one printshop shown in the customer directory.
    __tablename__ = "printshops"

    # Basic public shop details. Optional fields can be empty until the shop
    # provides them, name and location are required.
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(255), nullable=False)
    logo_path = db.Column(db.String(255), nullable=True)
    contact_phone = db.Column(db.String(30), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    business_hours = db.Column(db.String(255), nullable=True)

    # Optional link to the admin account that owns/manages this shop.
    admin_account_id = db.Column(
        db.Integer, db.ForeignKey("admin.account_id"), nullable=True
    )

    # These relationships let Python code get the shop's admin, staff, and
    # service/product rows without writing a join query by hand.
    admin = db.relationship("Admin", back_populates="printshops")
    staff_members = db.relationship("Staff", back_populates="printshop")
    offerings = db.relationship("PrintShopServices", back_populates="printshop")


class PrintShopServices(db.Model):
    __tablename__ = "printshops_services"

    # Link each offering to the printshop that provides it. The name is
    # required; description and customer choices are optional.
    id = db.Column(db.Integer, primary_key=True)
    printshop_id = db.Column(
        db.Integer, db.ForeignKey("printshops.id"), nullable=False
    )
    name = db.Column(db.String(120), nullable=False)
    # Separate work customers request ("service") from items they can order
    # ("product").
    category = db.Column(db.String(20), nullable=False, default="service")
    description = db.Column(db.Text, nullable=True)
    # Optional JSON data for choices such as paper size, color, quantity, or
    # finish. This can vary between offerings.
    options = db.Column(db.JSON, nullable=True)
    # Inactive rows stay in the database but should not be shown to customers.
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Link back to the printshop that owns this offering.
    printshop = db.relationship("PrintShop", back_populates="offerings")


class PrintRequest(db.Model):
    """A customer's request for one service from one printshop."""

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

    # Allow app code to access the staff member's account and assigned shop.
    account = db.relationship("Account", back_populates="staff")
    printshop = db.relationship("PrintShop", back_populates="staff_members")
