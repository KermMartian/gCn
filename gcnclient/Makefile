# Project: gcnclient
# Makefile created by Dev-C++ 4.9.9.2

CPP  = g++
CC   = gcc
RES  = 
OBJ  = main.o hiddata.o $(RES)
LINKOBJ  = main.o hiddata.o $(RES)
LIBS = -lusb  -g3 
BIN  = gcnclient
CXXFLAGS = $(CXXINCS)   -fexpensive-optimizations -O3 -g3
CFLAGS = $(INCS)   -fexpensive-optimizations -O3 -g3
RM = rm -f

.PHONY: all all-before all-after clean clean-custom

all: all-before gcnclient all-after


clean: clean-custom
	${RM} $(OBJ) $(BIN)

$(BIN): $(OBJ)
	$(CPP) $(LINKOBJ) -o "gcnclient" $(LIBS)

main.o: main.cpp
	$(CPP) -c main.cpp -o main.o $(CXXFLAGS)

hiddata.o: hiddata.c
	$(CPP) -c hiddata.c -o hiddata.o $(CXXFLAGS)
