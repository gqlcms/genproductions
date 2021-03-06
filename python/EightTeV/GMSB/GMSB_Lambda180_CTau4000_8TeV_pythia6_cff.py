import FWCore.ParameterSet.Config as cms

from Configuration.Generator.PythiaUEZ2starSettings_cfi import *

generator = cms.EDFilter("Pythia6GeneratorFilter",
    pythiaHepMCVerbosity = cms.untracked.bool(False),
    maxEventsToPrint = cms.untracked.int32(0),
    pythiaPylistVerbosity = cms.untracked.int32(0),
    filterEfficiency = cms.untracked.double(1.0),
    comEnergy = cms.double(8000.0),
    PythiaParameters = cms.PSet(
        pythiaUESettingsBlock,
        processParameters = cms.vstring(
            'MSEL=39                  ! All SUSY processes', 
            'IMSS(1) = 11             ! Spectrum from external SLHA file', 
            'IMSS(11) = 1             ! keeps gravitino mass from being overwritten',
            'IMSS(21) = 33            ! LUN number for SLHA File (must be 33)', 
            'IMSS(22) = 33            ! Read-in SLHA decay table',
            'PARJ(71)=4000.            ! for which ctau  4000 mm', 
            'RMSS(21) = 0             ! The gravitino mass'),    
   
        parameterSets = cms.vstring('pythiaUESettings', 
                                'processParameters',
                                'SLHAParameters'),
    
        SLHAParameters = cms.vstring('SLHAFILE = Configuration/Generator/data/GMSB_Lambda180_CTau4000_pythia6.slha')
        #SLHAParameters = cms.vstring('SLHAFILE = GMSB-8-TeV/8-TeV-Samples/python/GMSB_Lambda180_CTau4000_pythia6.slha')

        )
 )

configurationMetadata = cms.untracked.PSet(
    version = cms.untracked.string('$Revision: 1.1 $'),
    name = cms.untracked.string('$Source: Configuration/GenProduction/python/EightTeV/GMSB_Lambda180_CTau4000_8TeV_pythia6_cff.py,v $'),
    annotation = cms.untracked.string('GMSB Lambda=180TeV and ctau=4000 at 8 TeV')
)

ProductionFilterSequence = cms.Sequence(generator)
