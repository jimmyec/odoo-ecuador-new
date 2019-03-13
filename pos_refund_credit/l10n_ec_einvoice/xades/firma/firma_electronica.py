# -*- coding: utf-8 -*-
##############################################################################
#
#    E-Invoice Module - Ecuador
#    Copyright (C) 2014 VIRTUALSAMI CIA. LTDA. All Rights Reserved
#    alcides@virtualsami.com.ec
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from __future__ import unicode_literals
  
import unittest
import time
import logging
import os
import base64
import StringIO
import hashlib
import datetime
from pytz import timezone
from OpenSSL import crypto
from lxml import etree
from lxml.etree import DocumentInvalid

#from osv import osv, fields
#from tools import config
#from tools.translate import _
#from tools import ustr
import tools
from M2Crypto import BIO, EVP, RSA, X509, m2
from suds.client import Client
import decimal_precision as dp
import netsvc

SIGN_REF_TMPL = """
<ds:SignedInfo>
<ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"></ds:CanonicalizationMethod>
<ds:SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"></ds:SignatureMethod>
<ds:Reference Type="http://uri.etsi.org/01903#SignedProperties" URI="#Signature">
<ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"></ds:DigestMethod>
<ds:DigestValue>%(signature_digest_value)s</ds:DigestValue>
</ds:Reference>
<ds:Reference URI="#Certificate">
<ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"></ds:DigestMethod>
<ds:DigestValue>%(certificate_digest_value)s</ds:DigestValue>
</ds:Reference>
<ds:Reference URI="%(ref_uri)s">
<ds:Transforms>
<ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"></ds:Transform>
</ds:Transforms>
<ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"></ds:DigestMethod>
<ds:DigestValue>%(digest_value)s</ds:DigestValue>
</ds:Reference>
</ds:SignedInfo>"""

SIGNED_TMPL = """
<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:etsi="http://uri.etsi.org/01903/v1.3.2#">%(signed_info)s
<ds:SignatureValue>%(signature_value)s</ds:SignatureValue>%(key_info)s</ds:Signature>"""

KEY_INFO_RSA_TMPL = """
<ds:KeyInfo>
<ds:X509Data>
<ds:X509Certificate>
%(certificate)s</ds:X509Certificate>
</ds:X509Data>
<ds:KeyValue>
<ds:RSAKeyValue>
<ds:Modulus>
%(modulus)s</ds:Modulus>
<ds:Exponent>%(exponent)s</ds:Exponent>
</ds:RSAKeyValue>
</ds:KeyValue>
</ds:KeyInfo>
<ds:Object><etsi:QualifyingProperties Target="#Signature"><etsi:SignedProperties><etsi:SignedSignatureProperties><etsi:SigningTime>%(signingTime)s</etsi:SigningTime><etsi:SigningCertificate><etsi:Cert><etsi:CertDigest><ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"></ds:DigestMethod><ds:DigestValue>%(certificate_digest_value)s</ds:DigestValue></etsi:CertDigest><etsi:IssuerSerial><ds:X509IssuerName>%(issuer_name)s</ds:X509IssuerName><ds:X509SerialNumber>%(serial_number)s</ds:X509SerialNumber></etsi:IssuerSerial></etsi:Cert></etsi:SigningCertificate></etsi:SignedSignatureProperties><etsi:SignedDataObjectProperties><etsi:DataObjectFormat ObjectReference="#Reference"><etsi:Description>%(ref_uri)s</etsi:Description><etsi:MimeType>%(mime_type)s</etsi:MimeType></etsi:DataObjectFormat></etsi:SignedDataObjectProperties></etsi:SignedProperties></etsi:QualifyingProperties></ds:Object>
"""

class TestSignXML(unittest.TestCase):
    
    def canonicalize(self, xml):
        et = etree.parse(xml)
        output = StringIO.StringIO()
        et.write_c14n(output)
        return output.getvalue()
    
    def sha1_hash_digest(self, payload):
        return base64.b64encode(hashlib.sha1(payload).digest())

    def rsa_sign(self, xml, ref_uri, private_key, password=None, cert=None, mime_type='text/xml', c14n_exc=False, sign_template=SIGN_REF_TMPL, key_info_template=KEY_INFO_RSA_TMPL):
        ref_xml = self.canonicalize(xml)
        p12 = crypto.load_pkcs12(open(private_key, 'rb').read(), password)
        pem_string = crypto.dump_privatekey(crypto.FILETYPE_PEM, p12.get_privatekey())
        cer_string = crypto.dump_certificate(crypto.FILETYPE_PEM, p12.get_certificate())
        cer_string = cer_string.replace('-----BEGIN CERTIFICATE-----\n', '').replace('-----END CERTIFICATE-----\n', '')
        signed_info = sign_template % {'signature_digest_value': self.sha1_hash_digest(pem_string),
                                       'certificate_digest_value': self.sha1_hash_digest(cer_string),
                                       'ref_uri': ref_uri,
                                       'digest_value': self.sha1_hash_digest(ref_xml),
                                       }
        pkey = RSA.load_key_string(pem_string)
        signature = pkey.sign(hashlib.sha1(signed_info).digest())
        return {'ref_xml': ref_xml, 
                'ref_uri': ref_uri,
                'signed_info': signed_info,
                'signature_value': base64.b64encode(signature),
                'key_info': self.key_info(pkey, ref_uri, p12.get_certificate(), cer_string, mime_type, key_info_template),
                }

    def key_info(self, pkey, ref_uri, x509, cer_string, mime_type, key_info_template):
        exponent = base64.b64encode(pkey.e[4:])
        modulus = m2.bn_to_hex(m2.mpi_to_bn(pkey.n)).decode("hex").encode("base64")
        return key_info_template % {'modulus': modulus,
                                    'exponent': exponent,
                                    'certificate': cer_string,
                                    'certificate_digest_value': self.sha1_hash_digest(cer_string),
                                    'signingTime': datetime.datetime.now(timezone('America/Guayaquil')).isoformat(),
                                    'ref_uri': ref_uri,
                                    'mime_type': mime_type,
                                    'issuer_name': self.get_issuer(x509),
                                    'serial_number': x509.get_serial_number(),
                                    }

    def get_issuer(self, x509):
        return 'CN=' + x509.get_issuer().CN + ",L=" + x509.get_issuer().L + ",OU=" + x509.get_issuer().OU + ",O=" + x509.get_issuer().O + ",C=" + x509.get_issuer().C
    
 
    def sign_xml(self, fichero_xml):
        key_file = 'cesar_rolando_gonzalez_brito.p12'

        vars = self.rsa_sign(xml=fichero_xml, ref_uri='#comprobante', private_key=key_file, password="Fuserito21jun", mime_type='text/xml')
        firma = SIGNED_TMPL % vars
        firma_xml = etree.fromstring(firma)
        
        file_path_xmldsig = os.path.join(os.path.dirname(__file__), 'docs/xmldsig-core-schema.xsd')
        schema_file_xmldsig = open(file_path_xmldsig)
        xmlschema_doc_xmldsig = etree.parse(schema_file_xmldsig)
        xmlschema_xmldsig = etree.XMLSchema(xmlschema_doc_xmldsig)
        try:
            xmlschema_xmldsig.assertValid(firma_xml)
        except DocumentInvalid as e:
            raise Exception('Error de Datos', """El sistema generó la firma electrónica del XML pero la firma electrónica no pasa la validación XSD de xmldsig.
            \nEl siguiente error contiene el identificador o número de documento en conflicto:\n\n %s""" % str(e))
            
        file_path_xades = os.path.join(os.path.dirname(__file__), 'docs/XAdES1.2.2.xsd')
        schema_file_xades = open(file_path_xades)
        xmlschema_doc_xades = etree.parse(schema_file_xades)
        xmlschema_xades = etree.XMLSchema(xmlschema_doc_xades)
        try:
            xmlschema_xades.assertValid(firma_xml)
        except DocumentInvalid as e:
            raise Exception('Error de Datos', """El sistema generó la firma electrónica del XML pero la firma electrónica no pasa la validación XSD del estándar XadES_BES.
            \nEl siguiente error contiene el identificador o número de documento en conflicto:\n\n %s""" % str(e))
            
        tree = etree.parse(name)
        factura = tree.getroot()
        factura.append(firma_xml)
        tree = etree.ElementTree(factura)

        tree.write(name,pretty_print=True,xml_declaration=True,encoding='utf-8',method="xml")
            
        return True
