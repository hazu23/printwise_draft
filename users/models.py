from decimal import Decimal, InvalidOperation

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

    # These methods keep role checks inside the Account class. Routes can ask
    # an account what it is allowed to do instead of comparing role text many times.
    def has_role(self, role_name):
        """Return True when this account has the given role."""
        return self.role == role_name

    def is_customer(self):
        """Return True when this account is a customer."""
        return self.has_role("customer")

    def is_shop_worker(self):
        """Return True when this account is staff or an admin."""
        return self.role in {"staff", "admin"}

    def home_endpoint(self):
        """Return the Flask page name this account should see after logging in."""
        if self.is_customer():
            return "customer_bp.dashboard"
        if self.has_role("admin"):
            return "shop_requests.inbox"
        if self.has_role("staff"):
            return "staff_bp.index"
        return "customer_bp.index"

    def accessible_printshops(self):
        """Return the printshops this staff member or admin can manage."""
        if self.has_role("staff"):
            return [self.staff.printshop] if self.staff and self.staff.printshop else []

        if self.has_role("admin"):
            return sorted(self.admin.printshops, key=lambda shop: shop.name.lower()) if self.admin else []

        return []


class Customer(db.Model):
    __tablename__ = "customers"

    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), primary_key=True
    )
    phone_number = db.Column(db.String(30), nullable=True)
    profile_picture_path = db.Column(db.String(255), nullable=True)

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
    # One payment QR is configured per printshop. The name tells customers
    # which app or payment service to use, such as GCash, Maya, or QR Ph.
    payment_qr_name = db.Column(db.String(50), nullable=True)
    payment_qr_path = db.Column(db.String(255), nullable=True)
    payment_account_name = db.Column(db.String(100), nullable=True)
    payment_account_number = db.Column(db.String(30), nullable=True)
    # A printshop may offer one additional QR payment option.
    payment_qr_2_name = db.Column(db.String(50), nullable=True)
    payment_qr_2_path = db.Column(db.String(255), nullable=True)
    payment_qr_2_account_name = db.Column(db.String(100), nullable=True)
    payment_qr_2_account_number = db.Column(db.String(30), nullable=True)
    # Kept temporarily so older databases can be migrated without losing files.
    gcash_qr_path = db.Column(db.String(255), nullable=True)
    maya_qr_path = db.Column(db.String(255), nullable=True)

    admin_account_id = db.Column(
        db.Integer, db.ForeignKey("admin.account_id"), nullable=True
    )

    admin = db.relationship("Admin", back_populates="printshops")
    staff_members = db.relationship("Staff", back_populates="printshop")
    offerings = db.relationship("PrintShopServices", back_populates="printshop")

    # This method returns only active services in a predictable name order.
    def active_services(self):
        """Return this printshop's active services and products."""
        return sorted(
            (service for service in self.offerings if service.is_active),
            key=lambda service: service.name.lower(),
        )

    def payment_options(self):
        """Return each completely configured QR payment option."""
        options = []
        if self.payment_qr_name and self.payment_qr_path:
            options.append({
                "slot": "primary",
                "name": self.payment_qr_name,
                "path": self.payment_qr_path,
                "account_name": self.payment_account_name,
                "account_number": self.payment_account_number,
            })
        if self.payment_qr_2_name and self.payment_qr_2_path:
            options.append({
                "slot": "secondary",
                "name": self.payment_qr_2_name,
                "path": self.payment_qr_2_path,
                "account_name": self.payment_qr_2_account_name,
                "account_number": self.payment_qr_2_account_number,
            })
        return options


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

    # Some offerings are displayed in the directory but are not request types.
    def can_be_requested(self, hidden_service_names):
        """Return True when customers may use this service in a print request."""
        return self.is_active and self.name.strip().lower() not in hidden_service_names


class PrintRequest(db.Model):
    __tablename__ = "print_requests"

    id = db.Column(db.Integer, primary_key=True)
    customer_account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), nullable=True
    )
    # Walk-in customers may not have a PrintWise account. Their name and
    # optional contact are saved directly on the request instead.
    walk_in_customer_name = db.Column(db.String(100), nullable=True)
    walk_in_customer_contact = db.Column(db.String(255), nullable=True)
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
    # Staff or admins set this after checking the files and print options.
    # It remains empty until the printshop decides the final price.
    price = db.Column(db.Numeric(10, 2), nullable=True)
    payment_status = db.Column(db.String(20), nullable=False, default="unpaid")
    payment_method = db.Column(db.String(50), nullable=True)
    payment_receipt_path = db.Column(db.String(255), nullable=True)
    payment_submitted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    customer = db.relationship("Account")
    printshop = db.relationship("PrintShop")
    service = db.relationship("PrintShopServices")

    # These values are the only request statuses the system accepts.
    ALLOWED_STATUSES = {
        "pending", "accepted", "in_progress", "ready", "completed", "declined",
        "cancelled",
    }
    ALLOWED_PAYMENT_STATUSES = {
        "unpaid", "for_verification", "partially_paid", "paid"
    }

    def belongs_to_customer(self, account_id):
        """Return True when this request was made by the given customer."""
        return self.customer_account_id == account_id

    def belongs_to_any_printshop(self, shop_ids):
        """Return True when this request belongs to one of the given printshops."""
        return self.printshop_id in shop_ids

    def change_status(self, new_status):
        """Change status only when the supplied status is allowed."""
        clean_status = (new_status or "").strip().lower()
        if clean_status not in self.ALLOWED_STATUSES:
            return False
        self.status = clean_status
        return True

    def cancel_by_customer(self):
        """Cancel only before the printshop starts printing the request."""
        if self.status not in {"pending", "accepted"}:
            return False
        self.status = "cancelled"
        return True

    def set_price(self, new_price):
        """Save a valid peso amount and return True when it succeeds."""
        try:
            amount = Decimal(str(new_price).strip())
            if amount < Decimal("0.01") or amount > Decimal("99999999.99"):
                return False
            self.price = amount.quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return False
        return True

    def change_payment_status(self, new_status):
        """Change payment status only when the supplied value is allowed."""
        clean_status = (new_status or "").strip().lower()
        if clean_status not in self.ALLOWED_PAYMENT_STATUSES:
            return False
        self.payment_status = clean_status
        return True

    def submit_payment_receipt(self, payment_method, receipt_path):
        """Save a customer's QR payment receipt for staff verification."""
        clean_method = (payment_method or "").strip()
        if not clean_method or len(clean_method) > 50 or not receipt_path:
            return False
        self.payment_method = clean_method
        self.payment_receipt_path = receipt_path
        self.payment_status = "for_verification"
        self.payment_submitted_at = db.func.now()
        return True

    def uploaded_file_paths(self):
        """Return file paths as a list even if old data is missing or incorrect."""
        return self.file_paths if isinstance(self.file_paths, list) else []


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
