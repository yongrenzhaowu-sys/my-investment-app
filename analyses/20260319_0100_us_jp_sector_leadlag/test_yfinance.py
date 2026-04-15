import yfinance as yf
import pandas as pd

data = yf.download('XLB', start='2024-01-01', end='2024-01-10', progress=False, auto_adjust=True)
print("Raw columns:", data.columns.tolist())
print("Raw data:")
print(data.head())

data = data.reset_index()
print("\nAfter reset_index:", data.columns.tolist())

if isinstance(data.columns, pd.MultiIndex):
    print("MultiIndex detected, flattening...")
    data.columns = [col[0] if col[1] == '' else col[1] for col in data.columns]
    print("After flattening:", data.columns.tolist())

print("\nFinal data:")
print(data.head())
