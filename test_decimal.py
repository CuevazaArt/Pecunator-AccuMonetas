from decimal import Decimal

def format_to_string(val, step_size_str):
    val = Decimal(str(val))
    step_size = Decimal(str(step_size_str)) # keeping the string precision
    
    # Calculate remainder precisely
    remainder = val % step_size
    rounded = val - remainder
    
    # Format according to step_size exponent
    return f"{rounded.quantize(step_size):f}"

print("Price:", format_to_string(0.01234567, "0.00010000"))
print("Qty:", format_to_string(123.456, "1.00000000"))
print("Qty2:", format_to_string(123.456, "0.10000000"))
