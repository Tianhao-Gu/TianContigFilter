# -*- coding: utf-8 -*-
import os
import time
import unittest
from configparser import ConfigParser

from TianContigFilter.TianContigFilterImpl import TianContigFilter
from TianContigFilter.TianContigFilterServer import MethodContext
from TianContigFilter.authclient import KBaseAuth as _KBaseAuth

from installed_clients.WorkspaceClient import Workspace
from installed_clients.AssemblyUtilClient import AssemblyUtil


class TianContigFilterTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        token = os.environ.get('KB_AUTH_TOKEN', None)
        config_file = os.environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('TianContigFilter'):
            cls.cfg[nameval[0]] = nameval[1]
        # Getting username from Auth profile for token
        authServiceUrl = cls.cfg['auth-service-url']
        auth_client = _KBaseAuth(authServiceUrl)
        user_id = auth_client.get_user(token)
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': token,
                        'user_id': user_id,
                        'provenance': [
                            {'service': 'TianContigFilter',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = Workspace(cls.wsURL)
        cls.serviceImpl = TianContigFilter(cls.cfg)
        cls.scratch = cls.cfg['scratch']
        cls.callback_url = os.environ['SDK_CALLBACK_URL']
        suffix = int(time.time() * 1000)
        cls.wsName = "test_ContigFilter_" + str(suffix)
        ret = cls.wsClient.create_workspace({'workspace': cls.wsName})  # noqa

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    def load_fasta_file(self, filename, obj_name, contents):
        f = open(filename, 'w')
        f.write(contents)
        f.close()
        assemblyUtil = AssemblyUtil(self.callback_url)
        assembly_ref = assemblyUtil.save_assembly_from_fasta({'file': {'path': filename},
                                                              'workspace_name': self.wsName,
                                                              'assembly_name': obj_name
                                                              })
        return assembly_ref

    def test_run_ContigFilter_ok(self):

        # First load a test FASTA file as an KBase Assembly
        fasta_content = '>seq1 something soemthing asdf\n' \
                        'agcttttcat\n' \
                        '>seq2\n' \
                        'agctt\n' \
                        '>seq3\n' \
                        'agcttttcatgg'

        assembly_ref = self.load_fasta_file(os.path.join(self.scratch, 'test1.fasta'),
                                            'TestAssembly',
                                            fasta_content)

        # Second, call your implementation
        ret = self.serviceImpl.run_TianContigFilter(self.ctx,
                                                    {'workspace_name': self.wsName,
                                                     'assembly_input_ref': assembly_ref,
                                                     'min_length': 10
                                                     })

        # Validate the returned data
        self.assertEqual(ret[0]['n_initial_contigs'], 3)
        self.assertEqual(ret[0]['n_contigs_removed'], 1)
        self.assertEqual(ret[0]['n_contigs_remaining'], 2)

    def test_run_ContigFilter_err1(self):
        with self.assertRaises(ValueError) as errorContext:
            self.serviceImpl.run_TianContigFilter(self.ctx,
                                                  {'workspace_name': self.wsName,
                                                   'assembly_input_ref': '1/fake/3',
                                                   'min_length': '-10'})
        self.assertIn('min_length parameter cannot be negative', str(errorContext.exception))

    def test_run_ContigFilter_err2(self):
        with self.assertRaises(ValueError) as errorContext:
            self.serviceImpl.run_TianContigFilter(self.ctx,
                                                  {'workspace_name': self.wsName,
                                                   'assembly_input_ref': '1/fake/3',
                                                   'min_length': 'ten'})
        self.assertIn('Cannot parse integer from min_length parameter', str(errorContext.exception))

    def test_run_ContigFilter_err3(self):
        with self.assertRaises(ValueError) as errorContext:
            self.serviceImpl.run_TianContigFilter(self.ctx,
                                                  {'workspace_name': self.wsName,
                                                   'assembly_input_ref': '1/fake/3'})
        self.assertIn('Parameter min_length is not set in input arguments', str(errorContext.exception))
