# WarehousePro - Modern Warehouse Management System

A professional, commercial-grade Warehouse Management System built with Django. Features a modern, beautiful UI with gradient designs, comprehensive inventory tracking, FEFO allocation, batch processing, and real-time dashboard analytics.

## ✨ Features

### 🎨 Modern UI/UX
- **Beautiful Dashboard** with gradient KPI cards and real-time statistics
- **Professional Design** with deep navy/royal blue color scheme
- **Responsive Layout** with fixed sidebar navigation
- **Smooth Animations** and modern card designs
- **Status Badges** with color-coded states

### 📦 Inventory Management
- **Item Management** - Track products with SKU, name, description, and pricing
- **Batch Tracking** - FEFO (First Expired First Out) allocation
- **Lot Numbers** - Complete traceability with lot/batch tracking
- **Expiry Management** - Automated expiry date monitoring and alerts
- **Low Stock Alerts** - Real-time notifications for inventory levels

### 📋 Order Processing
- **Order Creation** - Simple and intuitive order entry
- **Automatic Allocation** - FEFO-based batch allocation
- **Order Fulfillment** - Pick, pack, ship, deliver workflow
- **Order Returns** - Complete return processing with restocking
- **Status Tracking** - Real-time order status updates

### 📊 Reports & Analytics
- **Dashboard Analytics** - KPI cards showing totals and pending orders
- **Recent Orders View** - Quick access to latest order activity
- **Stock Movement Reports** - Track all inventory transactions
- **Export to CSV/Excel** - Export items, batches, and orders
- **Date Filtering** - Filter exports by date ranges

### 🔍 Search & Filter
- **Item Search** - Quick search by name, SKU, category
- **Batch Search** - Filter by lot number, expiry dates
- **Customer Orders** - Search orders by customer name
- **Advanced Filters** - Multiple filter criteria support

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or higher
- pip (Python package installer)

### Installation

```powershell
# Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # On Windows
# source venv/bin/activate    # On Linux/Mac

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Load sample data (optional)
python manage.py load_sample_data

# Create superuser
python manage.py createsuperuser
# Username: admin
# Password: admin (or your choice)

# Start the development server
python manage.py runserver
```

Then open <http://127.0.0.1:8000/> in your browser.

**Default Login:** admin / admin (if you used the suggested credentials)

## 📁 Project Structure

```plaintext
wms_project/
├── inventory/              # Main inventory app
│   ├── models.py          # Database models (Item, Batch, Order, etc.)
│   ├── views.py           # View logic
│   ├── forms.py           # Django forms
│   ├── urls.py            # URL routing
│   ├── services/          # Business logic services
│   │   ├── allocation.py  # FEFO allocation algorithm
│   │   ├── batch_processor.py
│   │   └── notifications.py
│   ├── templates/         # HTML templates
│   │   └── inventory/
│   │       ├── base.html       # Base template with modern UI
│   │       ├── dashboard.html  # Main dashboard
│   │       ├── item_list.html
│   │       ├── batch_list.html
│   │       └── order_list.html
│   └── tests/            # Unit tests
├── wms_project/          # Django project settings
│   ├── settings.py       # Configuration
│   ├── urls.py           # Root URL config
│   └── wsgi.py           # WSGI config
├── sample_data/          # Sample CSV templates
├── manage.py             # Django management script
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🎯 Key Technologies

- **Django 5.1.6** - Web framework
- **SQLite** - Database (default, easily switchable to PostgreSQL)
- **Bootstrap 5.3.2** - UI framework
- **Bootstrap Icons 1.11.3** - Icon library
- **Chart.js 4.4.0** - Data visualization
- **htmx 1.9.10** - Dynamic interactions
- **Google Fonts (Inter)** - Modern typography

## 💻 Usage

### Dashboard
Navigate to the home page to see:
- Total items, batches, orders, and pending orders
- Quick action buttons for common tasks
- Recent orders table
- Low stock alerts
- Expiring batches warnings

### Managing Items
1. Go to **Items** → **View All Items**
2. Click **Add Item** to create new products
3. Edit or delete existing items as needed
4. Export items to CSV/Excel

### Receiving Stock
1. Click **Receive Stock** from dashboard or sidebar
2. Select an item and enter batch details
3. Specify quantity, lot number, and expiry date
4. Submit to add inventory

### Creating Orders
1. Click **Create Order** from dashboard
2. Select customer and item
3. Enter quantity needed
4. System automatically allocates from oldest expiring batches (FEFO)
5. Process through pick → pack → ship → deliver workflow

### Processing Returns
1. Navigate to **Process Return**
2. Select the original order
3. Enter return quantity and reason
4. System restocks inventory automatically

## 🔧 Configuration

### Database
Default: SQLite (`db.sqlite3`)

To use PostgreSQL, update `wms_project/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'warehousepro',
        'USER': 'your_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Static Files
```powershell
python manage.py collectstatic
```

## 📊 Sample Data

The project includes a management command to load sample data:

```powershell
python manage.py load_sample_data
```

This creates:
- 15 sample items (various products)
- 21 batches with different expiry dates
- 10 sample orders with different statuses

## 🧪 Running Tests

```powershell
python manage.py test inventory.tests
```

Tests include:
- FEFO allocation logic
- Concurrency handling
- Import validation
- Shipping workflows

## 📝 License

This project is open source and available under the MIT License.

## 👨‍💻 Author

Built with ❤️ for modern warehouse management

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

## 📧 Support

For support, email your-email@example.com or open an issue on GitHub.

---

**WarehousePro** - Professional Warehouse Management System © 2025

## Project layout

- `wms_project/` – Django project (settings, URLs, WSGI/ASGI)
- `inventory/` – App skeleton (models, views, admin, urls, templates, static)
- `requirements.txt` – Python dependencies
- `.gitignore` – Standard Python/Django ignores

## Notes

- SQLite by default: Lightweight for local dev; no extra services required.
- `django-q` is included for background task processing.
- Adjust settings in `wms_project/settings.py` as needed for your environment.
