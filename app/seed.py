import csv
import os
from datetime import datetime
from sqlalchemy.orm import Session
from database import engine, DBPosTransaction, SessionLocal, init_db

def load_pos_data():
    csv_path = "pos_transactions.csv"
    if not os.path.exists(csv_path):
        print(f"CSV {csv_path} not found.")
        return

    db = SessionLocal()
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            try:
                # 10-04-2026,12:15:05
                dt_str = f"{row['order_date']} {row['order_time']}"
                dt = datetime.strptime(dt_str, "%d-%m-%Y %H:%M:%S")
                
                txn = DBPosTransaction(
                    transaction_id=str(row['order_id']),
                    store_id=row['store_id'],
                    timestamp=dt,
                    basket_value_inr=float(row['total_amount'])
                )
                db.merge(txn) # use merge to avoid integrity errors on rerun
                count += 1
            except Exception as e:
                print(f"Error loading row: {e}")
                
        db.commit()
        print(f"Loaded {count} POS transactions.")
    db.close()

if __name__ == "__main__":
    init_db()
    load_pos_data()
