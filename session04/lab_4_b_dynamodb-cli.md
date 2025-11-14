# Lab 4.B: DynamoDB Employee Table with CLI and Python

## Overview
Create and manage a DynamoDB employee table using AWS CLI and Python (boto3). Learn DynamoDB's flexible schema by adding employees with different attributes, then build a Python application to query the data.

## Objectives
- Create a DynamoDB table with partition and sort keys
- Insert employee records with varying attributes (flexible schema)
- Query employees using CLI
- Build a Python application to query DynamoDB
- Clean up resources

## Prerequisites
- AWS CLI v2 configured
- Python 3 with boto3 installed
- IAM permissions for DynamoDB operations

---

## Variables

```bash
REGION=ap-southeast-2
TABLE_NAME=Employees
```

---

## Step 1: Create DynamoDB Table

```bash
# Create Employees table with EmployeeID as partition key and Department as sort key
aws dynamodb create-table \
  --table-name "$TABLE_NAME" \
  --attribute-definitions \
    AttributeName=EmployeeID,AttributeType=S \
    AttributeName=Department,AttributeType=S \
  --key-schema \
    AttributeName=EmployeeID,KeyType=HASH \
    AttributeName=Department,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION"
echo "Table creation initiated"

# Wait for table to be active
aws dynamodb wait table-exists \
  --table-name "$TABLE_NAME" \
  --region "$REGION"
echo "Table is active"
```

---

## Step 2: Insert Employee Records

```bash
# Insert employee 1 - Software Engineer with full attributes
aws dynamodb put-item \
  --table-name "$TABLE_NAME" \
  --item '{
    "EmployeeID": {"S": "E001"},
    "Department": {"S": "Engineering"},
    "Name": {"S": "Alice Johnson"},
    "Role": {"S": "Software Engineer"},
    "Salary": {"N": "95000"},
    "Age": {"N": "28"}
  }' \
  --region "$REGION"
echo "Employee E001 added"

# Insert employee 2 - HR Manager (no age attribute)
aws dynamodb put-item \
  --table-name "$TABLE_NAME" \
  --item '{
    "EmployeeID": {"S": "E002"},
    "Department": {"S": "HR"},
    "Name": {"S": "Bob Smith"},
    "Role": {"S": "HR Manager"},
    "Salary": {"N": "85000"}
  }' \
  --region "$REGION"
echo "Employee E002 added"

# Insert employee 3 - DevOps Engineer with all attributes
aws dynamodb put-item \
  --table-name "$TABLE_NAME" \
  --item '{
    "EmployeeID": {"S": "E003"},
    "Department": {"S": "Engineering"},
    "Name": {"S": "Carol Martinez"},
    "Role": {"S": "DevOps Engineer"},
    "Salary": {"N": "105000"},
    "Age": {"N": "32"}
  }' \
  --region "$REGION"
echo "Employee E003 added"

# Insert employee 4 - Financial Analyst (no salary attribute for privacy)
aws dynamodb put-item \
  --table-name "$TABLE_NAME" \
  --item '{
    "EmployeeID": {"S": "E004"},
    "Department": {"S": "Finance"},
    "Name": {"S": "David Lee"},
    "Role": {"S": "Financial Analyst"},
    "Age": {"N": "35"}
  }' \
  --region "$REGION"
echo "Employee E004 added"
```

---

## Step 3: Query Employees with CLI

```bash
# Get specific employee by EmployeeID and Department
aws dynamodb get-item \
  --table-name "$TABLE_NAME" \
  --key '{
    "EmployeeID": {"S": "E001"},
    "Department": {"S": "Engineering"}
  }' \
  --region "$REGION"
echo "Retrieved employee E001"

# Scan all employees in the table
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --region "$REGION"
echo "Scanned all employees"

# Filter employees by department (Engineering)
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --filter-expression "Department = :dept" \
  --expression-attribute-values '{":dept":{"S":"Engineering"}}' \
  --region "$REGION"
echo "Filtered employees in Engineering department"

# Filter employees by salary (above $90,000)
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --filter-expression "Salary >= :minSalary" \
  --expression-attribute-values '{":minSalary":{"N":"90000"}}' \
  --region "$REGION"
echo "Filtered high earners"
```

---

## Step 4: Create Python Application

```bash
# Create application directory structure
mkdir -p employee-app
cd employee-app

# Create query_employees.py file
cat > query_employees.py << 'EOF'
#!/usr/bin/env python3
"""Query employees from DynamoDB table"""
import boto3
from boto3.dynamodb.conditions import Attr
from decimal import Decimal

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
table = dynamodb.Table('Employees')

def get_employee(employee_id, department):
    """Get specific employee by ID and Department"""
    response = table.get_item(
        Key={'EmployeeID': employee_id, 'Department': department}
    )
    return response.get('Item')

def get_all_employees():
    """Get all employees from table"""
    response = table.scan()
    return response.get('Items', [])

def get_employees_by_department(department):
    """Get employees in specific department"""
    response = table.scan(
        FilterExpression=Attr('Department').eq(department)
    )
    return response.get('Items', [])

def get_high_earners(min_salary):
    """Get employees earning above specified salary"""
    response = table.scan(
        FilterExpression=Attr('Salary').gte(Decimal(str(min_salary)))
    )
    return response.get('Items', [])

def display_employee(emp):
    """Display employee information"""
    if not emp:
        print("Employee not found")
        return
    print(f"\nEmployee ID: {emp.get('EmployeeID', 'N/A')}")
    print(f"Name: {emp.get('Name', 'N/A')}")
    print(f"Department: {emp.get('Department', 'N/A')}")
    print(f"Role: {emp.get('Role', 'N/A')}")
    print(f"Salary: ${emp.get('Salary', 'N/A')}")
    print(f"Age: {emp.get('Age', 'N/A')}")
    print("-" * 40)

if __name__ == "__main__":
    print("=== Get Specific Employee ===")
    employee = get_employee('E001', 'Engineering')
    display_employee(employee)
    
    print("\n=== All Employees ===")
    for emp in get_all_employees():
        display_employee(emp)
    
    print("\n=== Engineering Department ===")
    for emp in get_employees_by_department('Engineering'):
        display_employee(emp)
    
    print("\n=== High Earners (>= $100,000) ===")
    for emp in get_high_earners(100000):
        display_employee(emp)
EOF

# Create add_employee.py file
cat > add_employee.py << 'EOF'
#!/usr/bin/env python3
"""Add new employee to DynamoDB table"""
import boto3
from decimal import Decimal

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
table = dynamodb.Table('Employees')

def add_employee(employee_id, department, name, role, salary=None, age=None):
    """Add new employee to table"""
    item = {
        'EmployeeID': employee_id,
        'Department': department,
        'Name': name,
        'Role': role
    }
    if salary:
        item['Salary'] = Decimal(str(salary))
    if age:
        item['Age'] = int(age)
    
    table.put_item(Item=item)
    print(f"Added employee {employee_id}")

if __name__ == "__main__":
    add_employee(
        employee_id='E005',
        department='Marketing',
        name='Emma Wilson',
        role='Marketing Manager',
        salary=88000,
        age=30
    )
EOF

# Create requirements.txt
cat > requirements.txt << 'EOF'
boto3>=1.26.0
EOF

# Make scripts executable
chmod +x query_employees.py add_employee.py

echo "Python application files created"
```

---

## Step 5: Run Python Application

```bash
# Install dependencies
pip install -r requirements.txt

# Query employees
python3 query_employees.py

# Add new employee
python3 add_employee.py

# Query again to see new employee
python3 query_employees.py
```

---

## Step 6: Cleanup

```bash
# Delete the DynamoDB table
aws dynamodb delete-table \
  --table-name "$TABLE_NAME" \
  --region "$REGION"
echo "Table deletion initiated"

# Wait for table deletion to complete
aws dynamodb wait table-not-exists \
  --table-name "$TABLE_NAME" \
  --region "$REGION"
echo "Table deleted"

# Clean up application directory
cd ..
rm -rf employee-app
echo "Cleanup complete"
```

---

## Summary

This lab demonstrated:
- **DynamoDB table creation** with partition (EmployeeID) and sort keys (Department)
- **Flexible schema** - employees can have different attributes
- **CLI operations** for inserting and querying data
- **Python boto3** for programmatic table access
- **Real-world example** with employee data demonstrating NoSQL flexibility

### Key Concepts

**Partition Key (EmployeeID):**
- Unique identifier for data distribution
- Used for direct item lookups

**Sort Key (Department):**
- Allows multiple items with same partition key
- Enables range queries and filtering

**Flexible Schema:**
- E001: All attributes (ID, Name, Role, Salary, Age)
- E002: Missing Age
- E004: Missing Salary
- DynamoDB allows items with different attributes in same table

**Query vs Scan:**
- **get-item**: Fast lookup by exact key
- **scan**: Reads entire table (expensive)
- **scan with filter**: Filters after reading (use sparingly)

**Best Practices:**
- Use PAY_PER_REQUEST for unpredictable workloads
- Design keys for your access patterns
- Minimize scans on large tables
- Handle missing attributes in application code

---
