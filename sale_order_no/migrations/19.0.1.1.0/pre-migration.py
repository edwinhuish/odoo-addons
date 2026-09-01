# -*- coding: utf-8 -*-
"""Pre-migration script for sale_order_no 19.0.1.1.0

Field renames:
- sale_order.customer_code        -> sale_order.buyer_ref
- sale_order.customer_seq_num     -> sale_order.buyer_order_idx
- sale_order.customer_doc_no      -> sale_order.order_no

Field removal:
- sale_order.customer_doc_year    (removed, year is read from date_order)
"""

import logging

_logger = logging.getLogger(__name__)


def _rename_column(cr, old_name, new_name):
    """Rename a PostgreSQL column if it exists and the target does not."""
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'sale_order' AND column_name = %s;
    """, (old_name,))
    if not cr.fetchone():
        return

    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'sale_order' AND column_name = %s;
    """, (new_name,))
    if cr.fetchone():
        _logger.warning(
            "Column %s already exists in sale_order, skipping rename from %s.",
            new_name, old_name,
        )
        return

    cr.execute(
        "ALTER TABLE sale_order RENAME COLUMN %s TO %s;" % (old_name, new_name)
    )
    _logger.info("Renamed sale_order column %s -> %s.", old_name, new_name)


def _drop_column(cr, name):
    """Drop a PostgreSQL column if it exists."""
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'sale_order' AND column_name = %s;
    """, (name,))
    if not cr.fetchone():
        return

    cr.execute("ALTER TABLE sale_order DROP COLUMN %s;" % name)
    _logger.info("Dropped sale_order column %s.", name)


def _update_ir_model_fields(cr, old_name, new_name, model='sale.order'):
    """Update the ir_model_fields record to match the new field name."""
    cr.execute("""
        UPDATE ir_model_fields
        SET name = %s
        WHERE name = %s AND model = %s;
    """, (new_name, old_name, model))


def _remove_ir_model_field(cr, name, model='sale.order'):
    """Remove the ir_model_fields record for a deleted field."""
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE name = %s AND model = %s;
    """, (name, model))


def migrate(cr, version):
    _logger.info("Running sale_order_no pre-migration to 19.0.1.1.0.")

    # Rename database columns to preserve existing data.
    _rename_column(cr, 'customer_code', 'buyer_ref')
    _rename_column(cr, 'customer_seq_num', 'buyer_order_idx')
    _rename_column(cr, 'customer_doc_no', 'order_no')

    # Remove the now-unused year snapshot column.
    _drop_column(cr, 'customer_doc_year')

    # Keep ir_model_fields consistent with the new Python model.
    _update_ir_model_fields(cr, 'customer_code', 'buyer_ref')
    _update_ir_model_fields(cr, 'customer_seq_num', 'buyer_order_idx')
    _update_ir_model_fields(cr, 'customer_doc_no', 'order_no')
    _remove_ir_model_field(cr, 'customer_doc_year')

    _logger.info("sale_order_no pre-migration completed.")
