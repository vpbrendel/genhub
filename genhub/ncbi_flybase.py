#!/usr/bin/env python
#
# -----------------------------------------------------------------------------
# Copyright (c) 2015   Daniel Standage <daniel.standage@gmail.com>
# Copyright (c) 2015   Indiana University
#
# This file is part of genhub (http://github.com/standage/genhub) and is
# licensed under the BSD 3-clause license: see LICENSE.txt.
# -----------------------------------------------------------------------------

"""Genome database implementation for FlyBase data at NCBI."""

from __future__ import print_function
import filecmp
import gzip
import os
import re
import subprocess
import sys
import genhub


class FlyBaseDB(genhub.genomedb.GenomeDB):

    def __init__(self, label, conf, workdir='.'):
        super(FlyBaseDB, self).__init__(label, conf, workdir)
        assert self.config['source'] == 'ncbi_flybase'
        assert 'species' in self.config
        species = self.config['species'].replace(' ', '_')
        self.specbase = ('ftp://ftp.ncbi.nih.gov/genomes/'
                         'Drosophila_melanogaster/RELEASE_5_48')
        self.format_gdna = self.format_fasta
        self.format_prot = self.format_fasta

    def __repr__(self):
        return 'FlyBase@NCBI'

    @property
    def gdnafilename(self):
        return '%s.orig.fa.gz' % self.label

    @property
    def gdnaurl(self):
        urls = list()
        for acc in self.config['accessions']:
            url = '%s/%s.fna' % (self.specbase, acc)
            urls.append(url)
        return urls

    @property
    def gff3url(self):
        urls = list()
        for acc in self.config['accessions']:
            url = '%s/%s.gff' % (self.specbase, acc)
            urls.append(url)
        return urls

    @property
    def proturl(self):
        urls = list()
        for acc in self.config['accessions']:
            url = '%s/%s.faa' % (self.specbase, acc)
            urls.append(url)
        return urls

    def download_gff3(self, logstream=sys.stderr):  # pragma: no cover
        """Override the default download task."""
        subprocess.call(['mkdir', '-p', self.dbdir])
        if logstream is not None:
            logmsg = '[GenHub: %s] ' % self.config['species']
            logmsg += 'download genome annotation from %r' % self
            print(logmsg, file=logstream)

        command = ['gt', 'gff3', '-sort', '-tidy', '-force', '-gzip', '-o',
                   '%s' % self.gff3path]
        for url, acc in zip(self.gff3url, self.config['accessions']):
            tempout = '%s/%s.gff.gz' % (self.dbdir, os.path.basename(acc))
            genhub.download.url_download(url, tempout, compress=True)
            command.append(tempout)
        logfile = open('%s.log' % self.gff3path, 'w')
        proc = subprocess.Popen(command, stderr=subprocess.PIPE)
        proc.wait()
        for line in proc.stderr:
            print(line, end='', file=logfile)
        assert proc.returncode == 0, ('command failed, check the log '
                                      '(%s.log): %s' %
                                      (self.gff3path, ' '.join(command)))

    def format_fasta(self, instream, outstream, logstream=sys.stderr):
        for line in instream:
            if line.startswith('>'):
                pattern = '>gi\|\d+\|(ref|gb)\|([^\|]+)\S+'
                line = re.sub(pattern, '>\g<2>', line)
            print(line, end='', file=outstream)

    def format_gff3(self, logstream=sys.stderr, debug=False):
        cmds = list()
        cmds.append('gunzip -c %s' % self.gff3path)
        excludefile = genhub.conf.conf_filter_file(self.config)
        cmds.append('grep -vf %s' % excludefile.name)
        cmds.append('genhub-fix-trna.py')
        cmds.append('tidygff3')
        cmds.append('genhub-format-gff3.py --source ncbi_flybase -')
        cmds.append('gt gff3 -sort -tidy -o %s -force' % self.gff3file)

        commands = ' | '.join(cmds)
        if debug:  # pragma: no cover
            print('DEBUG: running command: %s' % commands, file=logstream)
        proc = subprocess.Popen(commands, shell=True, universal_newlines=True,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        for line in stderr.split('\n'):  # pragma: no cover
            if 'has not been previously introduced' not in line and \
               'does not begin with "##gff-version"' not in line and \
               line != '':
                print(line, file=logstream)
        assert proc.returncode == 0, \
            'annot cleanup command failed: %s' % commands
        os.unlink(excludefile.name)


# -----------------------------------------------------------------------------
# Unit tests
# -----------------------------------------------------------------------------


def test_chromosomes():
    """NCBI/FlyBase chromosome download"""

    label, config = genhub.conf.load_one('conf/HymHub/Dmel.yml')
    testurls = ['ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_X/NC_004354.fna',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_2/NT_033778.fna',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_2/NT_033779.fna',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_3/NT_033777.fna',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_3/NT_037436.fna',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_4/NC_004353.fna']
    testpath = './Dmel/Dmel.orig.fa.gz'
    dmel_db = FlyBaseDB(label, config)
    assert dmel_db.gdnaurl == testurls, \
        'chromosome URL mismatch\n%s\n%s' % (dmel_db.gdnaurl, testurls)
    assert dmel_db.gdnapath == testpath, \
        'chromosome path mismatch\n%s\n%s' % (dmel_db.gdnapath, testpath)
    assert '%r' % dmel_db == 'FlyBase@NCBI'
    assert dmel_db.compress_gdna is True


def test_annot():
    """NCBI/FlyBase annotation download"""

    label, config = genhub.conf.load_one('conf/HymHub/Dmel.yml')
    testurls = ['ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_X/NC_004354.gff',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_2/NT_033778.gff',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_2/NT_033779.gff',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_3/NT_033777.gff',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_3/NT_037436.gff',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_4/NC_004353.gff']
    testpath = './Dmel/dmel-5.48-ncbi.gff3.gz'
    dmel_db = FlyBaseDB(label, config)
    assert dmel_db.gff3url == testurls, \
        'annotation URL mismatch\n%s\n%s' % (dmel_db.gff3url, testurls)
    assert dmel_db.gff3path == testpath, \
        'annotation path mismatch\n%s\n%s' % (dmel_db.gff3path, testpath)
    assert dmel_db.compress_gff3 is True


def test_proteins():
    """NCBI/FlyBase protein download"""
    label, config = genhub.conf.load_one('conf/HymHub/Dmel.yml')
    testurls = ['ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_X/NC_004354.faa',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_2/NT_033778.faa',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_2/NT_033779.faa',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_3/NT_033777.faa',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_3/NT_037436.faa',
                'ftp://ftp.ncbi.nih.gov/genomes/Drosophila_melanogaster/'
                'RELEASE_5_48/CHR_4/NC_004353.faa']
    testpath = './Dmel/protein.fa.gz'
    dmel_db = FlyBaseDB(label, config)
    assert dmel_db.proturl == testurls, \
        'protein URL mismatch\n%s\n%s' % (dmel_db.proturl, testurls)
    assert dmel_db.protpath == testpath, \
        'protein path mismatch\n%s\n%s' % (dmel_db.protpath, testpath)
    assert dmel_db.compress_prot is True


def test_format():
    """Task drivers"""
    label, conf = genhub.conf.load_one('conf/HymHub/Dmel.yml')
    dmel_db = FlyBaseDB(label, conf, workdir='testdata/demo-workdir')
    dmel_db.format(logstream=None, verify=False)


def test_gdna_format():
    """NCBI/FlyBase gDNA formatting"""

    label, conf = genhub.conf.load_one('conf/HymHub/Dmel.yml')
    dmel_db = FlyBaseDB(label, conf, workdir='testdata/demo-workdir')
    dmel_db.preprocess_gdna(logstream=None, verify=False)
    outfile = 'testdata/demo-workdir/Dmel/Dmel.gdna.fa'
    testoutfile = 'testdata/fasta/dmel-fb-gdna-ut-out.fa'
    assert filecmp.cmp(testoutfile, outfile), 'Dmel gDNA formatting failed'


def test_annot_format():
    """NCBI/FlyBase annotation formatting"""

    label, conf = genhub.conf.load_one('conf/HymHub/Dmel.yml')
    aech_db = FlyBaseDB(label, conf, workdir='testdata/demo-workdir')
    aech_db.preprocess_gff3(logstream=None, verify=False)
    outfile = 'testdata/demo-workdir/Dmel/Dmel.gff3'
    testfile = 'testdata/gff3/ncbi-format-dmel.gff3'
    assert filecmp.cmp(outfile, testfile), 'Dmel annotation formatting failed'


def test_prot_format():
    """NCBI/FlyBase protein formatting"""

    label, conf = genhub.conf.load_one('conf/HymHub/Dmel.yml')
    dmel_db = FlyBaseDB(label, conf, workdir='testdata/demo-workdir')
    dmel_db.preprocess_prot(logstream=None, verify=False)
    outfile = 'testdata/demo-workdir/Dmel/Dmel.all.prot.fa'
    testoutfile = 'testdata/fasta/dmel-fb-prot-ut-out.fa'
    assert filecmp.cmp(testoutfile, outfile), 'Dmel protein formatting failed'
