COQC ?= coqc
COQMAKEFILE ?= coq_makefile
BUSYCOQ_DIR ?= ..
COQMFFLAGS := -Q $(BUSYCOQ_DIR) BusyCoq

# Same layout as verify/CounterClass1/Makefile. In verify/BBi8_3x4 the parent
# mapping already binds this directory to BusyCoq.BBi8_3x4. The second mapping
# is only needed when this folder is built from a separate working tree.
# BB34.vo and Individual34.vo must be built in the parent directory first.
ifneq ($(abspath .),$(abspath $(BUSYCOQ_DIR)/BBi8_3x4))
COQMFFLAGS += -Q . BusyCoq.BBi8_3x4
endif

ALLVFILES := $(sort $(wildcard *.v))

all: check

Makefile.coq: Makefile $(ALLVFILES)
	$(COQMAKEFILE) $(COQMFFLAGS) -o Makefile.coq $(ALLVFILES)

check: Makefile.coq
	$(MAKE) -f Makefile.coq

clean::
	if [ -e Makefile.coq ]; then $(MAKE) -f Makefile.coq cleanall; fi
	$(RM) $(wildcard Makefile.coq Makefile.coq.conf)

-include Makefile.coq

.PHONY: all check clean
