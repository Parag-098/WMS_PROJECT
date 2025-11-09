#!/usr/bin/env python
"""Fix order detail template to show workflow properly."""

# Read the current template
with open('inventory/templates/inventory/order_detail.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old workflow section
old_workflow = """            {% if order.status == 'new' %}
            <a href="{% url 'inventory:order-allocate' order.pk %}" class="btn btn-success">
                <i class="bi bi-check-circle"></i> Allocate Stock
            </a>
            {% elif order.status == 'allocated' %}
            <a href="{% url 'inventory:order-pick' order.pk %}" class="btn btn-warning">
                <i class="bi bi-box-seam"></i> Pick
            </a>
            {% if user.is_staff %}
            <a href="{% url 'inventory:order-deallocate' order.pk %}" class="btn btn-danger">
                <i class="bi bi-x-circle"></i> Deallocate
            </a>
            {% endif %}
            {% elif order.status == 'picked' %}
            <a href="{% url 'inventory:order-pack' order.pk %}" class="btn btn-info">
                <i class="bi bi-box"></i> Pack
            </a>
            {% if user.is_staff %}
            <a href="{% url 'inventory:order-ship' order.pk %}" class="btn btn-primary">
                <i class="bi bi-truck"></i> Ship
            </a>
            {% endif %}
            {% elif order.status == 'shipped' and user.is_staff %}
            <a href="{% url 'inventory:order-deliver' order.pk %}" class="btn btn-success">
                <i class="bi bi-check-circle"></i> Mark as Delivered
            </a>
            {% endif %}"""

# Define the new improved workflow section with numbered steps
new_workflow = """            {# === WORKFLOW BUTTONS === #}
            {% if order.status == 'new' %}
            <a href="{% url 'inventory:order-allocate' order.pk %}" class="btn btn-success">
                <i class="bi bi-check-circle"></i> Step 1: Allocate Stock
            </a>
            
            {% elif order.status == 'allocated' %}
            <a href="{% url 'inventory:order-pick' order.pk %}" class="btn btn-warning">
                <i class="bi bi-box-seam"></i> Step 2: Pick Items
            </a>
            {% if user.is_staff %}
            <a href="{% url 'inventory:order-deallocate' order.pk %}" class="btn btn-outline-danger">
                <i class="bi bi-x-circle"></i> Deallocate
            </a>
            {% endif %}
            
            {% elif order.status == 'picked' %}
            <a href="{% url 'inventory:order-pack' order.pk %}" class="btn btn-info">
                <i class="bi bi-box"></i> Step 3: Pack Items
            </a>
            {% if user.is_staff %}
            <small class="text-muted ms-2">or</small>
            <a href="{% url 'inventory:order-ship' order.pk %}" class="btn btn-outline-primary">
                <i class="bi bi-truck"></i> Skip to Ship
            </a>
            {% endif %}
            
            {% elif order.status == 'shipped' %}
            {% if user.is_staff %}
            <a href="{% url 'inventory:order-deliver' order.pk %}" class="btn btn-success">
                <i class="bi bi-check-circle-fill"></i> Step 4: Mark as Delivered
            </a>
            {% else %}
            <span class="badge bg-primary fs-6"><i class="bi bi-truck"></i> In Transit</span>
            {% endif %}
            
            {% elif order.status == 'delivered' %}
            <span class="badge bg-success fs-6"><i class="bi bi-check-circle-fill"></i> Order Completed</span>
            
            {% elif order.status == 'cancelled' %}
            <span class="badge bg-secondary fs-6"><i class="bi bi-x-circle-fill"></i> Order Cancelled</span>
            {% endif %}"""

# Replace the workflow section
if old_workflow in content:
    content = content.replace(old_workflow, new_workflow)
    print("✓ Workflow section replaced successfully")
else:
    print("✗ Could not find exact workflow section - content may have changed")
    print("\nSearching for alternative patterns...")
    
# Write the updated content back
with open('inventory/templates/inventory/order_detail.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✓ Template file updated!")
print("\nWorkflow improvements:")
print("  • Added numbered steps (Step 1, 2, 3, 4)")
print("  • Made Pack primary action, Ship as staff override")
print("  • Added completion badges for delivered/cancelled")
print("  • Improved button styling and hierarchy")
