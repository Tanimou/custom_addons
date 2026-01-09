# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

""" Jeko Payment Provider Constants """

# API Configuration
JEKO_API_URL = "https://api.jeko.africa/partner_api/"

# Controller URLs
JEKO_SUCCESS_URL = '/payment/jeko/success'
JEKO_ERROR_URL = '/payment/jeko/error'
JEKO_WEBHOOK_URL = '/payment/jeko/webhook'
JEKO_POS_WEBHOOK_URL = '/payment/jeko/pos/webhook'

# Supported Currencies
SUPPORTED_CURRENCIES = ['XOF', 'XAF']

# Default Payment Method Codes
DEFAULT_PAYMENT_METHOD_CODES = ['jeko']