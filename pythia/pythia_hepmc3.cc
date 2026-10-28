// Minimal Pythia8 -> HepMC3 driver for the mucoll-slurm Pythia chains.
// Matt LeBlanc, Brown University 2026
// matt_leblanc@brown.edu
//
// Usage:  pythia_hepmc3 CARD.cmnd OUTPUT.hepmc NEVENTS SEED
//
// All physics settings live in the .cmnd card; NEVENTS and SEED given on the
// command line override whatever the card says, so one card serves every job.
// Output is HepMC3 ASCII, which ddsim reads directly (HEPMC3FileReader).
//
// Build (inside the mucoll-sim image, done automatically by run_chain_pythia.sh):
//   g++ pythia_hepmc3.cc -o pythia_hepmc3 $(pythia8-config --cxxflags --ldflags)
//       $(HepMC3-config --cflags --libs) -Wl,-rpath,$(HepMC3-config --libdir)

#include <cstdlib>
#include <iostream>
#include <string>

#include "Pythia8/Pythia.h"
#include "Pythia8Plugins/HepMC3.h"

using namespace Pythia8;

int main(int argc, char* argv[]) {
  if (argc != 5) {
    std::cerr << "Usage: " << argv[0]
              << " CARD.cmnd OUTPUT.hepmc NEVENTS SEED" << std::endl;
    return 1;
  }
  const std::string card = argv[1];
  const std::string output = argv[2];
  const int nEvents = std::atoi(argv[3]);
  const int seed = std::atoi(argv[4]);

  Pythia pythia;
  if (!pythia.readFile(card)) {
    std::cerr << "ERROR: could not read card " << card << std::endl;
    return 1;
  }
  // Pythia accepts seeds in [0, 900000000]; 0 would mean "seed from the clock".
  pythia.readString("Random:setSeed = on");
  pythia.readString("Random:seed = " + std::to_string(seed));
  pythia.readString("Main:numberOfEvents = " + std::to_string(nEvents));
  if (!pythia.init()) {
    std::cerr << "ERROR: Pythia initialization failed" << std::endl;
    return 1;
  }

  Pythia8ToHepMC toHepMC(output);

  const int nAbort = pythia.mode("Main:timesAllowErrors");
  int nErrors = 0;
  int nWritten = 0;
  while (nWritten < nEvents) {
    if (!pythia.next()) {
      if (++nErrors < nAbort) continue;
      std::cerr << "ERROR: too many failed events, aborting" << std::endl;
      break;
    }
    toHepMC.writeNextEvent(pythia);
    ++nWritten;
  }

  pythia.stat();
  std::cout << "Wrote " << nWritten << " events to " << output << std::endl;
  std::cout << "sigma = " << pythia.info.sigmaGen() * 1e9 << " +- "
            << pythia.info.sigmaErr() * 1e9 << " pb" << std::endl;
  return nWritten == nEvents ? 0 : 1;
}
