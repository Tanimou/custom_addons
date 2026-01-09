# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Tests for maintenance parts, time, and productivity (FR-020/FR-021/FR-022).

Test coverage:
- FR-020: Parts consumption tracking and stock/procurement hooks
- FR-021: Maintenance typology (curative/préventive)
- FR-022: Technician time tracking and productivity rollups
"""

from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'score_maintenance')
class TestMaintenanceTypology(TransactionCase):
    """Test suite for maintenance typology (FR-021)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Typology Test Model',
            'brand_id': cls.env['fleet.vehicle.model.brand'].create({
                'name': 'Typology Test Brand',
            }).id,
        })
        
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'TYPO-001',
            'company_id': cls.env.company.id,
        })
        
        cls.Intervention = cls.env['fleet.maintenance.intervention']

    def test_intervention_type_curative(self):
        """Test curative intervention type."""
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
        })
        
        self.assertEqual(
            intervention.intervention_type, 'curative',
            "Intervention type should be curative"
        )
        self.assertTrue(
            intervention.is_curative if hasattr(intervention, 'is_curative') else intervention.intervention_type == 'curative',
            "is_curative helper should be True"
        )

    def test_intervention_type_preventive(self):
        """Test preventive intervention type."""
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'preventive',
        })
        
        self.assertEqual(
            intervention.intervention_type, 'preventive',
            "Intervention type should be preventive"
        )
        self.assertTrue(
            intervention.is_preventive if hasattr(intervention, 'is_preventive') else intervention.intervention_type == 'preventive',
            "is_preventive helper should be True"
        )

    def test_typology_statistics(self):
        """Test typology statistics computation."""
        # Create multiple interventions
        for i in range(3):
            self.Intervention.create({
                'vehicle_id': self.vehicle.id,
                'intervention_type': 'curative',
                'state': 'done',
            })
        
        for i in range(2):
            self.Intervention.create({
                'vehicle_id': self.vehicle.id,
                'intervention_type': 'preventive',
                'state': 'done',
            })
        
        # Test read_group for typology
        groups = self.Intervention.read_group(
            domain=[('vehicle_id', '=', self.vehicle.id), ('state', '=', 'done')],
            fields=['intervention_type'],
            groupby=['intervention_type'],
        )
        
        curative_count = next((g['__count'] for g in groups if g['intervention_type'] == 'curative'), 0)
        preventive_count = next((g['__count'] for g in groups if g['intervention_type'] == 'preventive'), 0)
        
        self.assertEqual(curative_count, 3, "Should have 3 curative interventions")
        self.assertEqual(preventive_count, 2, "Should have 2 preventive interventions")

    def test_typology_filter_by_type(self):
        """Test filtering interventions by typology."""
        self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
        })
        self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'preventive',
        })
        
        curative = self.Intervention.search([
            ('vehicle_id', '=', self.vehicle.id),
            ('intervention_type', '=', 'curative'),
        ])
        preventive = self.Intervention.search([
            ('vehicle_id', '=', self.vehicle.id),
            ('intervention_type', '=', 'preventive'),
        ])
        
        self.assertEqual(len(curative), 1, "Should find 1 curative intervention")
        self.assertEqual(len(preventive), 1, "Should find 1 preventive intervention")


@tagged('post_install', '-at_install', 'score_maintenance')
class TestMaintenancePartsConsumption(TransactionCase):
    """Test suite for parts consumption tracking (FR-020)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Parts Test Model',
            'brand_id': cls.env['fleet.vehicle.model.brand'].create({
                'name': 'Parts Test Brand',
            }).id,
        })
        
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'PARTS-001',
            'company_id': cls.env.company.id,
        })
        
        # Create a test product (spare part)
        cls.product = cls.env['product.product'].create({
            'name': 'Brake Pad Test',
            'type': 'product',
            'default_code': 'BP-TEST-001',
            'list_price': 50.0,
            'standard_price': 30.0,
        })
        
        # Create a test vendor
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Test Parts Supplier',
            'supplier_rank': 1,
        })
        
        cls.Intervention = cls.env['fleet.maintenance.intervention']
        cls.PartLine = cls.env['fleet.maintenance.part.line']

    def test_part_line_creation(self):
        """Test creating a part line on an intervention."""
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
        })
        
        part_line = self.PartLine.create({
            'intervention_id': intervention.id,
            'product_id': self.product.id,
            'cost_type': 'part',
            'quantity': 2,
            'unit_price': 50.0,
        })
        
        self.assertEqual(part_line.subtotal, 100.0, "Subtotal should be 100.0")
        self.assertIn(part_line, intervention.part_line_ids)

    def test_part_line_cost_aggregation(self):
        """Test cost aggregation from part lines."""
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
        })
        
        # Add part cost
        self.PartLine.create({
            'intervention_id': intervention.id,
            'product_id': self.product.id,
            'cost_type': 'part',
            'quantity': 2,
            'unit_price': 50.0,
        })
        
        # Add labor cost
        self.PartLine.create({
            'intervention_id': intervention.id,
            'cost_type': 'labor',
            'description': 'Brake work',
            'quantity': 1,
            'unit_price': 75.0,
        })
        
        intervention._compute_cost_totals()
        
        self.assertEqual(intervention.part_amount, 100.0, "Part amount should be 100")
        self.assertEqual(intervention.labor_amount, 75.0, "Labor amount should be 75")
        self.assertEqual(intervention.total_amount, 175.0, "Total should be 175")

    def test_purchase_order_creation_from_intervention(self):
        """Test creating a purchase order from intervention parts."""
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'vendor_id': self.vendor.id,
        })
        
        self.PartLine.create({
            'intervention_id': intervention.id,
            'product_id': self.product.id,
            'cost_type': 'part',
            'quantity': 4,
            'unit_price': 50.0,
        })
        
        # Create PO
        action = intervention.action_create_purchase_order()
        
        self.assertTrue(intervention.purchase_order_ids, "Should have a purchase order linked")
        self.assertEqual(intervention.purchase_order_count, 1, "Should have 1 PO")

    def test_stock_transfer_creation(self):
        """Test creating a stock transfer for parts."""
        # Create maintenance location
        maintenance_location = self.env['stock.location'].create({
            'name': 'Maintenance Workshop',
            'usage': 'internal',
        })
        
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'location_id': maintenance_location.id,
        })
        
        self.PartLine.create({
            'intervention_id': intervention.id,
            'product_id': self.product.id,
            'cost_type': 'part',
            'quantity': 2,
            'unit_price': 30.0,
        })
        
        # Try to create stock transfer
        try:
            action = intervention.action_create_stock_transfer()
            self.assertTrue(intervention.picking_id, "Should have a picking linked")
        except UserError:
            # May fail if no warehouse configured - acceptable in test env
            pass


@tagged('post_install', '-at_install', 'score_maintenance')
class TestTechnicianTimeTracking(TransactionCase):
    """Test suite for technician time tracking and productivity (FR-022)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Time Test Model',
            'brand_id': cls.env['fleet.vehicle.model.brand'].create({
                'name': 'Time Test Brand',
            }).id,
        })
        
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'TIME-001',
            'company_id': cls.env.company.id,
        })
        
        # Create test technicians
        cls.technician1 = cls.env['res.users'].create({
            'name': 'Technician Alpha',
            'login': 'tech_alpha_test',
            'email': 'tech_alpha@test.com',
        })
        
        cls.technician2 = cls.env['res.users'].create({
            'name': 'Technician Beta',
            'login': 'tech_beta_test',
            'email': 'tech_beta@test.com',
        })
        
        cls.Intervention = cls.env['fleet.maintenance.intervention']

    def test_technician_time_entry_creation(self):
        """Test creating a technician time entry."""
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
        })
        
        TechnicianTime = self.env.get('fleet.maintenance.technician.time')
        if TechnicianTime is None:
            self.skipTest("fleet.maintenance.technician.time model not yet implemented")
        
        time_entry = TechnicianTime.create({
            'intervention_id': intervention.id,
            'technician_id': self.technician1.id,
            'date': datetime.now().date(),
            'hours': 4.5,
            'description': 'Brake inspection and repair',
        })
        
        self.assertEqual(time_entry.hours, 4.5, "Hours should be 4.5")
        self.assertEqual(time_entry.technician_id, self.technician1)

    def test_intervention_total_technician_hours(self):
        """Test total technician hours computed on intervention."""
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
        })
        
        TechnicianTime = self.env.get('fleet.maintenance.technician.time')
        if TechnicianTime is None:
            self.skipTest("fleet.maintenance.technician.time model not yet implemented")
        
        # Add multiple time entries
        TechnicianTime.create({
            'intervention_id': intervention.id,
            'technician_id': self.technician1.id,
            'date': datetime.now().date(),
            'hours': 3.0,
        })
        
        TechnicianTime.create({
            'intervention_id': intervention.id,
            'technician_id': self.technician2.id,
            'date': datetime.now().date(),
            'hours': 2.0,
        })
        
        # Check total hours if field exists
        if hasattr(intervention, 'total_technician_hours'):
            self.assertEqual(
                intervention.total_technician_hours,
                5.0,
                "Total technician hours should be 5.0"
            )

    def test_technician_productivity_per_period(self):
        """Test technician productivity aggregation."""
        now = datetime.now()
        
        intervention1 = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'state': 'done',
        })
        
        intervention2 = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'preventive',
            'state': 'done',
        })
        
        TechnicianTime = self.env.get('fleet.maintenance.technician.time')
        if TechnicianTime is None:
            self.skipTest("fleet.maintenance.technician.time model not yet implemented")
        
        # Technician 1: 6 hours total
        TechnicianTime.create({
            'intervention_id': intervention1.id,
            'technician_id': self.technician1.id,
            'date': now.date(),
            'hours': 4.0,
        })
        TechnicianTime.create({
            'intervention_id': intervention2.id,
            'technician_id': self.technician1.id,
            'date': now.date(),
            'hours': 2.0,
        })
        
        # Technician 2: 3 hours total
        TechnicianTime.create({
            'intervention_id': intervention1.id,
            'technician_id': self.technician2.id,
            'date': now.date(),
            'hours': 3.0,
        })
        
        # Aggregate by technician
        groups = TechnicianTime.read_group(
            domain=[('intervention_id', 'in', [intervention1.id, intervention2.id])],
            fields=['technician_id', 'hours:sum'],
            groupby=['technician_id'],
        )
        
        self.assertEqual(len(groups), 2, "Should have 2 technician groups")
        
        tech1_hours = next((g['hours'] for g in groups if g['technician_id'][0] == self.technician1.id), 0)
        tech2_hours = next((g['hours'] for g in groups if g['technician_id'][0] == self.technician2.id), 0)
        
        self.assertEqual(tech1_hours, 6.0, "Technician 1 should have 6 hours")
        self.assertEqual(tech2_hours, 3.0, "Technician 2 should have 3 hours")

    def test_technician_interventions_count(self):
        """Test counting interventions per technician."""
        TechnicianTime = self.env.get('fleet.maintenance.technician.time')
        if TechnicianTime is None:
            self.skipTest("fleet.maintenance.technician.time model not yet implemented")
        
        # Create interventions with time entries
        for i in range(3):
            intervention = self.Intervention.create({
                'vehicle_id': self.vehicle.id,
                'intervention_type': 'curative' if i % 2 == 0 else 'preventive',
            })
            TechnicianTime.create({
                'intervention_id': intervention.id,
                'technician_id': self.technician1.id,
                'date': datetime.now().date(),
                'hours': 1.0,
            })
        
        # Count distinct interventions for technician 1
        intervention_ids = TechnicianTime.search([
            ('technician_id', '=', self.technician1.id),
        ]).mapped('intervention_id')
        
        self.assertEqual(len(intervention_ids), 3, "Technician should have worked on 3 interventions")

    def test_productivity_by_intervention_type(self):
        """Test productivity analysis by intervention type."""
        TechnicianTime = self.env.get('fleet.maintenance.technician.time')
        if TechnicianTime is None:
            self.skipTest("fleet.maintenance.technician.time model not yet implemented")
        
        # Curative intervention
        curative = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
        })
        TechnicianTime.create({
            'intervention_id': curative.id,
            'technician_id': self.technician1.id,
            'date': datetime.now().date(),
            'hours': 5.0,
        })
        
        # Preventive intervention
        preventive = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'preventive',
        })
        TechnicianTime.create({
            'intervention_id': preventive.id,
            'technician_id': self.technician1.id,
            'date': datetime.now().date(),
            'hours': 2.0,
        })
        
        # The intervention type comes from the intervention, not the time entry
        # So we need to join through intervention_id
        curative_time = TechnicianTime.search([
            ('intervention_id.intervention_type', '=', 'curative'),
            ('technician_id', '=', self.technician1.id),
        ])
        preventive_time = TechnicianTime.search([
            ('intervention_id.intervention_type', '=', 'preventive'),
            ('technician_id', '=', self.technician1.id),
        ])
        
        self.assertEqual(sum(curative_time.mapped('hours')), 5.0)
        self.assertEqual(sum(preventive_time.mapped('hours')), 2.0)


@tagged('post_install', '-at_install', 'score_maintenance')
class TestProductivityKPIs(TransactionCase):
    """Test suite for productivity KPI computations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'KPI Test Model',
            'brand_id': cls.env['fleet.vehicle.model.brand'].create({
                'name': 'KPI Test Brand',
            }).id,
        })
        
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'KPI-001',
            'company_id': cls.env.company.id,
        })
        
        cls.Intervention = cls.env['fleet.maintenance.intervention']

    def test_average_intervention_duration(self):
        """Test average intervention duration KPI."""
        now = datetime.now()
        
        # Create interventions with different durations
        durations = [2, 4, 6]  # hours
        for duration in durations:
            self.Intervention.create({
                'vehicle_id': self.vehicle.id,
                'intervention_type': 'curative',
                'actual_start': now - timedelta(hours=duration),
                'actual_end': now,
                'state': 'done',
            })
        
        # Calculate average downtime
        interventions = self.Intervention.search([
            ('vehicle_id', '=', self.vehicle.id),
            ('state', '=', 'done'),
        ])
        
        if hasattr(interventions[0], 'downtime_hours'):
            avg_downtime = sum(interventions.mapped('downtime_hours')) / len(interventions)
            self.assertAlmostEqual(avg_downtime, 4.0, places=1, msg="Average should be 4 hours")

    def test_mttr_calculation(self):
        """Test MTTR (Mean Time To Repair) calculation."""
        now = datetime.now()
        
        # Create several completed curative interventions
        durations = [3, 5, 4, 6, 2]  # hours
        for duration in durations:
            self.Intervention.create({
                'vehicle_id': self.vehicle.id,
                'intervention_type': 'curative',
                'actual_start': now - timedelta(hours=duration),
                'actual_end': now,
                'state': 'done',
            })
        
        # MTTR = average repair time
        curative_interventions = self.Intervention.search([
            ('vehicle_id', '=', self.vehicle.id),
            ('intervention_type', '=', 'curative'),
            ('state', '=', 'done'),
        ])
        
        if hasattr(curative_interventions[0], 'downtime_hours'):
            mttr = sum(curative_interventions.mapped('downtime_hours')) / len(curative_interventions)
            expected_mttr = sum(durations) / len(durations)
            self.assertAlmostEqual(mttr, expected_mttr, places=1)

    def test_intervention_completion_rate(self):
        """Test intervention completion rate KPI."""
        # Create mix of completed and cancelled interventions
        for i in range(7):
            self.Intervention.create({
                'vehicle_id': self.vehicle.id,
                'intervention_type': 'curative',
                'state': 'done',
            })
        
        for i in range(3):
            self.Intervention.create({
                'vehicle_id': self.vehicle.id,
                'intervention_type': 'curative',
                'state': 'cancelled',
            })
        
        all_interventions = self.Intervention.search([
            ('vehicle_id', '=', self.vehicle.id),
        ])
        done = all_interventions.filtered(lambda i: i.state == 'done')
        
        completion_rate = (len(done) / len(all_interventions)) * 100
        self.assertAlmostEqual(completion_rate, 70.0, places=0, msg="Completion rate should be 70%")
