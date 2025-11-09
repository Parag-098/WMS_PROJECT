# Search Features Implementation Guide

## What Was Changed

### Removed:
- ❌ Barcode search functionality from navbar
- ❌ Quick search input box
- ❌ BarcodeSearchView API endpoint
- ❌ Old scanner templates (lot_scanner.html, item_scanner.html, customer_scanner.html)

### Added:
✅ **Three New Search Features with Excel & CSV Export:**

## 1. Lot/Batch Search
**URL:** `/lot-search/`
**Purpose:** Search lot numbers to view detailed batch information and transaction history

### Features:
- Date range filtering for transaction history
- Large input field for manual entry
- Complete batch information display:
  - Lot number, item details, dates
  - Initial vs available quantities
  - Current status with color coding
- Full transaction history for the batch
- **Excel & CSV Export:** Generates detailed reports with:
  - Batch information
  - Complete transaction log (filtered by date range if specified)
  - Formatted with headers and styling

### How to Use:
1. Navigate to "Search" → "Lot Search" in navbar
2. Enter a lot number
3. Optionally select start/end date to filter transactions
4. View all batch details and transactions
5. Click "Export to Excel" or "Export CSV" for detailed report

## 2. Item Search
**URL:** `/item-search/`
**Purpose:** Search item SKUs for comprehensive stock analysis

### Features:
- Date range filtering for transaction history
- Item details and current stock status
- Visual stock level indicator (red/yellow/green)
- All batches for the item with availability
- Active allocations (reserved stock)
- Recent transactions (filtered by date range if specified)
- Similar item suggestions when SKU not found
- **Excel & CSV Export:** Generates multi-sheet/detailed reports:
  - Item summary and totals
  - All batches with details
  - Transaction history

### How to Use:
1. Navigate to "Search" → "Item Search" in navbar
2. Enter an item SKU
3. Optionally select start/end date to filter transactions
4. View comprehensive stock information
5. Click "Export to Excel" or "Export CSV" for full analysis

## 3. Customer Search
**URL:** `/customer-search/`
**Purpose:** Search customers to view order history and statistics

### Features:
- Date range filtering for orders
- Customer order summary cards:
  - Total orders count
  - Total value spent
  - Average order value
- Complete order history table (filtered by date range if specified)
- All order items breakdown
- Status and priority indicators
- **Excel & CSV Export:** Generates reports with:
  - Order list with dates, status, values
  - Summary totals
  - Formatted with colors and styling

### How to Use:
1. Navigate to "Search" → "Customer Search" in navbar
2. Enter customer name (partial match supported)
3. Optionally select start/end date to filter orders
4. View order history and statistics
5. Click "Export to Excel" or "Export CSV" for detailed report

## Export Features (Excel & CSV)

All three search pages include **"Export to Excel"** and **"Export CSV"** buttons:

### Excel Export Features:
- Professional formatting with colored headers
- Auto-adjusted column widths
- Multiple sheets (where applicable)
- Summary sections with totals
- Date/time formatting
- Proper data types (numbers, dates, text)

### CSV Export Features:
- Plain-text format for easy import into other tools
- Same data as Excel exports
- Date range filtering applied
- Lightweight and universal compatibility

### File Naming:
- Lot Search: `lot_{lot_number}_report.xlsx` / `.csv`
- Item Search: `item_{sku}_report.xlsx` / `.csv`
- Customer Search: `customer_{name}_orders.xlsx` / `.csv`

## Navigation

New "Search" dropdown menu in navbar with three options:
- 🔍 Lot Search
- 📦 Item Search
- 👤 Customer Search

## Technical Details

### New Views Added:
1. `LotSearchView` - Template view for lot search with date filtering
2. `ItemSearchView` - Template view for item search with date filtering and suggestions
3. `CustomerSearchView` - Template view for customer search with date filtering
4. `ExportLotReportView` - Excel export for lots
5. `ExportItemReportView` - Excel export for items (multi-sheet)
6. `ExportCustomerReportView` - Excel export for customers
7. `ExportLotReportCSVView` - CSV export for lots
8. `ExportItemReportCSVView` - CSV export for items
9. `ExportCustomerReportCSVView` - CSV export for customers

### Dependencies:
- `openpyxl` - For Excel file generation (installed)
- Built-in `csv` module - For CSV generation

### Templates Created:
1. `/inventory/templates/inventory/lot_search.html`
2. `/inventory/templates/inventory/item_search.html`
3. `/inventory/templates/inventory/customer_search.html`

### URL Patterns Added:
```
/lot-search/
/item-search/
/customer-search/
/export/lot-report/?lot_number=XXX&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
/export/item-report/?item_sku=XXX&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
/export/customer-report/?customer_name=XXX&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
/export/lot-report.csv?lot_number=XXX&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
/export/item-report.csv?item_sku=XXX&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
/export/customer-report.csv?customer_name=XXX&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

## Benefits

### For Warehouse Staff:
- Quick lookup of lot/batch information
- Comprehensive item stock analysis
- Fast customer order history access
- Professional reports for management

### For Analysis:
- Detailed Excel reports for offline analysis
- Multi-sheet workbooks with organized data
- Easy to share with stakeholders
- Historical transaction tracking

### For Management:
- Customer ordering patterns
- Stock movement analysis
- Batch lifecycle tracking
- Export capabilities for reporting

## Usage Scenarios

### Scenario 1: Quality Control Issue
1. Use **Lot Search** to find affected batch
2. View all transaction history (filter by date if needed)
3. Export to Excel or CSV to share with QC team
4. Identify all orders that received the batch

### Scenario 2: Stock Analysis
1. Use **Item Search** to check specific product
2. View all batches (FEFO order)
3. See active allocations
4. Export multi-sheet report for analysis

### Scenario 3: Customer Service
1. Customer calls about their orders
2. Use **Customer Search** to find all orders
3. Filter by date range if needed
4. View complete order history
5. Export to Excel or CSV for detailed review
6. Calculate total business value

## Status Color Indicators

### Stock Levels:
- 🔴 **Red:** Out of stock or critical
- 🟡 **Yellow:** Low stock (below threshold)
- 🟢 **Green:** Healthy stock levels

### Order Status:
- 🟡 **Yellow:** Pending
- 🔵 **Blue:** Allocated
- 🔵 **Primary:** Picked
- ⚫ **Secondary:** Packed
- 🟢 **Green:** Shipped/Delivered

### Transaction Types:
- 🔵 **Primary:** Receive
- 🟡 **Warning:** Reserve
- 🟢 **Success:** Ship
- 🔵 **Info:** Return
- ⚫ **Secondary:** Adjust

## System Integration

All search pages integrate with existing:
- Manual Queue/Stack allocation backend
- Transaction logging system
- Order management system
- Batch tracking system
- User authentication

No changes to core allocation algorithms - only new search/reporting/analysis features added with date filtering capabilities.
