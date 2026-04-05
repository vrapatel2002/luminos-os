CC = gcc
SCANNER = wayland-scanner

CFLAGS = -O2 -Wall -Wextra -Wno-unused-parameter \
  $(shell pkg-config --cflags wayland-client wayland-egl egl glesv2 libdrm xkbcommon)

LIBS = $(shell pkg-config --libs wayland-client wayland-egl egl glesv2 libdrm xkbcommon) \
  -lpthread -lm

PROTO_DIR = protocols
PROTO_XML = $(PROTO_DIR)/wlr-layer-shell-unstable-v1.xml

# Generated protocol files
PROTO_HEADER = wlr-layer-shell-unstable-v1-client-protocol.h
PROTO_CODE   = wlr-layer-shell-unstable-v1-protocol.c

SRCS = main.c wayland.c egl.c renderer.c input.c socket.c power.c $(PROTO_CODE)
OBJS = $(SRCS:.c=.o)
TARGET = luminos-live-wallpaper

INSTALL_BIN = /usr/local/bin
INSTALL_PRESETS = /usr/share/luminos/live-wallpaper/presets

all: $(TARGET)

# Generate protocol header from XML
$(PROTO_HEADER): $(PROTO_XML)
	$(SCANNER) client-header $(PROTO_XML) $(PROTO_HEADER)

# Generate protocol implementation from XML
$(PROTO_CODE): $(PROTO_XML)
	$(SCANNER) private-code $(PROTO_XML) $(PROTO_CODE)

# Compile .c to .o
%.o: %.c $(PROTO_HEADER)
	$(CC) $(CFLAGS) -c -o $@ $<

# Link
$(TARGET): $(OBJS)
	$(CC) -o $@ $(OBJS) $(LIBS)

install: $(TARGET)
	install -Dm755 $(TARGET) $(DESTDIR)$(INSTALL_BIN)/$(TARGET)
	install -Dm644 presets/particles.glsl $(DESTDIR)$(INSTALL_PRESETS)/particles.glsl
	install -Dm644 presets/aurora.glsl    $(DESTDIR)$(INSTALL_PRESETS)/aurora.glsl
	install -Dm644 presets/geometric.glsl $(DESTDIR)$(INSTALL_PRESETS)/geometric.glsl

uninstall:
	rm -f $(DESTDIR)$(INSTALL_BIN)/$(TARGET)
	rm -rf $(DESTDIR)$(INSTALL_PRESETS)

clean:
	rm -f $(TARGET) $(OBJS) $(PROTO_HEADER) $(PROTO_CODE)

.PHONY: all install uninstall clean
