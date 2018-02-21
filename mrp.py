# -*- coding: utf-8 -*-

from openerp.osv import fields, osv
from openerp.tools.translate import _


class mrp_production_extend(osv.osv):
    _inherit = ['mrp.production']

    # Override _make_consume_line_from_data to set the location_id per material
    def _make_consume_line_from_data(self, cr, uid, production, product, uom_id, qty, context=None):
        stock_move = self.pool.get('stock.move')
        loc_obj = self.pool.get('stock.location')
        # Internal shipment is created for Stockable and Consumer Products
        if product.type not in ('product', 'consu'):
            return False

        product_uom_qty = qty
        destination_location_id = production.product_id.property_stock_production.id
        move_ids = []
        pending_qty = qty
        product_id = product.id
        if product_id:
            # Get all locations with stock of that product and not reserved
            quant_model = self.pool['stock.quant']
            stock_quant_ids = quant_model.search(cr, uid, [('product_id', '=', product_id), ('qty', '>', 0), ('reservation_id', '=', False)])
            stock_quants = quant_model.browse(cr, uid, stock_quant_ids)
            locations = []
            # Store all locations with available product
            for i in stock_quants:
                # Save the children locations of mrp source location
                if i.location_id.id not in locations and i.location_id.location_id.id == production.location_src_id.id:
                    locations.append(i.location_id.id)
            # Loop all locations with available product
            for i in locations:
                if pending_qty == 0:
                    break
                # Take routing location as a Source Location.
                source_location_id = production.location_src_id.id
                prod_location_id = source_location_id
                prev_move = False
                if production.routing_id:
                    routing = production.routing_id
                else:
                    routing = production.bom_id.routing_id
                if routing and routing.location_id and routing.location_id.id != source_location_id:
                    source_location_id = routing.location_id.id
                    prev_move = True

                # Get a location with enough stock of the product
                stock_quant_ids = quant_model.search(cr, uid, [('product_id', '=', product_id), ('qty', '>', 0), ('reservation_id', '=', False), ('location_id', '=', i)])
                stock_quants = quant_model.browse(cr, uid, stock_quant_ids)
                for i in stock_quants:
                    if pending_qty > 0:
                        source_location_id = i.location_id.id
                        if i.qty <= pending_qty:
                            product_uom_qty = i.qty
                        else:
                            # Pick only the needed qty
                            product_uom_qty = pending_qty
                        # Update the pending_qty
                        pending_qty -= product_uom_qty
                        move_id = stock_move.create(cr, uid, {
                            'name': production.name,
                            'date': production.date_planned,
                            'date_expected': production.date_planned,
                            'product_id': product.id,
                            'product_uom_qty': product_uom_qty,
                            'product_uom': uom_id,
                            'location_id': source_location_id,
                            'location_dest_id': destination_location_id,
                            'company_id': production.company_id.id,
                            'procure_method': prev_move and 'make_to_stock' or self._get_raw_material_procure_method(cr, uid, product, location_id=source_location_id,
                                                                                                                     location_dest_id=destination_location_id, context=context),  # Make_to_stock avoids creating procurement
                            'raw_material_production_id': production.id,
                            # this saves us a browse in create()
                            'price_unit': product.standard_price,
                            'origin': production.name,
                            'warehouse_id': loc_obj.get_warehouse(cr, uid, production.location_src_id, context=context),
                            'group_id': production.move_prod_id.group_id.id,
                        }, context=context)
                        if prev_move:
                            prev_move = self._create_previous_move(cr, uid, move_id, product, prod_location_id, source_location_id, context=context)
                            stock_move.action_confirm(cr, uid, [prev_move], context=context)
                        move_ids.append(move_id)
            # There is not enough stock. Create new line with the pending quantity and the parent location as source.
            if pending_qty > 0:
                product_uom_qty = pending_qty
                source_location_id = production.location_src_id.id
                pending_qty -= product_uom_qty
                # Take routing location as a Source Location.
                source_location_id = production.location_src_id.id
                prod_location_id = source_location_id
                prev_move = False
                if production.routing_id:
                    routing = production.routing_id
                else:
                    routing = production.bom_id.routing_id
                if routing and routing.location_id and routing.location_id.id != source_location_id:
                    source_location_id = routing.location_id.id
                    prev_move = True
                move_id = stock_move.create(cr, uid, {
                    'name': production.name,
                    'date': production.date_planned,
                    'date_expected': production.date_planned,
                    'product_id': product.id,
                    'product_uom_qty': product_uom_qty,
                    'product_uom': uom_id,
                    'location_id': source_location_id,
                    'location_dest_id': destination_location_id,
                    'company_id': production.company_id.id,
                    'procure_method': prev_move and 'make_to_stock' or self._get_raw_material_procure_method(cr, uid, product, location_id=source_location_id,
                                                                                                             location_dest_id=destination_location_id, context=context),  # Make_to_stock avoids creating procurement
                    'raw_material_production_id': production.id,
                    # this saves us a browse in create()
                    'price_unit': product.standard_price,
                    'origin': production.name,
                    'warehouse_id': loc_obj.get_warehouse(cr, uid, production.location_src_id, context=context),
                    'group_id': production.move_prod_id.group_id.id,
                }, context=context)
                if prev_move:
                    prev_move = self._create_previous_move(cr, uid, move_id, product, prod_location_id, source_location_id, context=context)
                    stock_move.action_confirm(cr, uid, [prev_move], context=context)
                move_ids.append(move_id)

        return move_ids

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirms production order.
        @return: Newly generated Shipment Id.
        """
        user_lang = self.pool.get('res.users').browse(cr, uid, [uid]).partner_id.lang
        context = dict(context, lang=user_lang)
        uncompute_ids = filter(lambda x: x, [not x.product_lines and x.id or False for x in self.browse(cr, uid, ids, context=context)])
        self.action_compute(cr, uid, uncompute_ids, context=context)
        for production in self.browse(cr, uid, ids, context=context):
            self._make_production_produce_line(cr, uid, production, context=context)
            stock_moves = []
            for line in production.product_lines:
                if line.product_id.type in ['product', 'consu']:
                    # Create as many lines as necessary
                    stock_move_ids = self._make_production_consume_line(cr, uid, line, context=context)
                    for stock_move_id in stock_move_ids:
                        stock_moves.append(stock_move_id)

            if stock_moves:
                self.pool.get('stock.move').action_confirm(cr, uid, stock_moves, context=context)
            production.write({'state': 'confirmed'})
        return 0
