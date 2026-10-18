# Default object files (can be extended in project Makefile)
C_OBJECTS ?= $(addprefix $(BUILDDIR)/,$(C_SOURCES:.c=.o))
CXX_OBJECTS ?= $(addprefix $(BUILDDIR)/,$(CXX_SOURCES:.cpp=.o))
PYTHON_OBJECTS ?= $(addprefix $(BUILDDIR)/,$(PYTHON_SOURCES))

CFLAGS += \
	--std=gnu11 \
	-pedantic \
	-Wall \
	-Werror \
	-Wextra \
	-Wfloat-equal \
	-Wno-error=unused-parameter \
	-Wpointer-arith \
	-Wshadow \
	-Wswitch-enum \
	-Wundef \
	-Wwrite-strings

CXXFLAGS += \
	--std=c++17 \
	-pedantic \
	-Wall \
	-Weffc++ \
	-Werror \
	-Wextra \
	-Wno-error=effc++ \
	-Wno-error=unused-parameter

# Use CXX for linking when C++ objects are present, otherwise use CC
LINKER = $(if $(CXX_OBJECTS),$(CXX),$(CC))
LINK_FLAGS = $(if $(CXX_OBJECTS),$(CXXFLAGS),$(CFLAGS))

# Ensure build directory exists
$(shell mkdir -p $(BUILDDIR))

# Default target for C/C++ projects
ifneq ($(strip $(C_OBJECTS) $(CXX_OBJECTS)),)
$(BUILDDIR)/$(TARGET): $(C_OBJECTS) $(CXX_OBJECTS)
	$(LINKER) $(LINK_FLAGS) -o $@ $^ $(LDFLAGS)
endif

# Default target for Python projects
ifneq ($(strip $(PYTHON_OBJECTS)),)
ifeq ($(strip $(C_OBJECTS) $(CXX_OBJECTS)),)
$(BUILDDIR)/$(TARGET): $(PYTHON_OBJECTS)
	cp $(BUILDDIR)/main.py $(BUILDDIR)/$(TARGET)
endif
endif

# Pattern rule for compiling .c files
$(BUILDDIR)/%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Pattern rule for compiling .cpp files
$(BUILDDIR)/%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Pattern rule for copying .py files
$(BUILDDIR)/%.py: %.py
	cp $< $@

clean:
	rm -f $(BUILDDIR)/$(TARGET) $(C_OBJECTS) $(CXX_OBJECTS) $(PYTHON_OBJECTS)

.PHONY: clean
