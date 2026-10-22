from . import db


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # customer, staff, or admin

    customer = db.relationship("Customer", back_populates="account", uselist=False)
    staff = db.relationship("Staff", back_populates="account", uselist=False)
    admin = db.relationship("Admin", back_populates="account", uselist=False)


class Customer(db.Model):
    __tablename__ = "customers"

    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), primary_key=True
    )

    account = db.relationship("Account", back_populates="customer")


class Admin(db.Model):
    __tablename__ = "admin"

    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), primary_key=True
    )

    account = db.relationship("Account", back_populates="admin")
    printshops = db.relationship("PrintShop", back_populates="admin")


class PrintShop(db.Model):
    __tablename__ = "printshops"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    admin_account_id = db.Column(
        db.Integer, db.ForeignKey("admin.account_id"), nullable=False
    )

    admin = db.relationship("Admin", back_populates="printshops")
    staff_members = db.relationship("Staff", back_populates="printshop")


class Staff(db.Model):
    __tablename__ = "staff"

    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), primary_key=True
    )
    printshop_id = db.Column(
        db.Integer, db.ForeignKey("printshops.id"), nullable=False
    )

    account = db.relationship("Account", back_populates="staff")
    printshop = db.relationship("PrintShop", back_populates="staff_members")