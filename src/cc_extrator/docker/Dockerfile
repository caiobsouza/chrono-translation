FROM gcc:13

ARG CT_VERSION=1.15.8
ARG CT_SHA256=4bdd0fde47006e5d797eeeed5a49dac32789287dafac6e0776fe20c4ae252197

RUN curl -fsSL "https://bisqwit.iki.fi/src/arch/chronotools-${CT_VERSION}.tar.bz2" -o /tmp/ct.tar.bz2 \
    && echo "${CT_SHA256}  /tmp/ct.tar.bz2" | sha256sum -c - \
    && mkdir /src \
    && tar xjf /tmp/ct.tar.bz2 -C /src --strip-components=1 \
    && rm /tmp/ct.tar.bz2

WORKDIR /src

# Chronotools generates .depend with a racy script that sometimes corrupts
# the file. Header dependency tracking is useless for a one-shot build, so an
# empty .depend skips the generation, and the one generated header it would
# have tracked is built explicitly.
RUN touch .depend \
    && make eventdata.inc \
    && make -j"$(nproc)" ctdump ctinsert utils/unmakeips utils/fixchecksum \
    && install ctdump ctinsert utils/unmakeips utils/fixchecksum /usr/local/bin/

# Default config: the sample from the tarball with four changes.
# - The variable-width 8px font is disabled (its renderer crashes on the
#   current toolchain).
# - dump_events is disabled. The sample recompiles event $017 (the game reset
#   event, used by the Finnish translation to change player names). The
#   recompiled event breaks the boot of the US ROM and leaves a black screen.
# - attempt_unwrap is disabled. With it on, ctdump strips the original line
#   breaks and ctinsert re-wraps every string to a generic 240px width, which
#   overflows the narrower text boxes. Off keeps the game's own line breaks.
# - rebuild is enabled. With the original dictionary reapplied, even the untouched
#   English script overflows six text pages and ctinsert reports ERROR lines. A
#   dictionary rebuilt for the script saves about 34 percent instead of 25 percent,
#   and a translation needs its own dictionary anyway.
RUN mkdir -p /opt/chronotools \
    && sed -e 's/^font8vfn /#font8vfn /' \
           -e 's/^prerender_vwf8 = true/prerender_vwf8 = false/' \
           -e 's/^dump_events/#dump_events/' \
           -e 's/^attempt_unwrap = true/attempt_unwrap = false/' \
           -e 's/^rebuild\( *\)= false/rebuild\1= true/' \
        etc/ct.cfg > /opt/chronotools/ct.cfg

WORKDIR /work
