# Transforms the live Caddyfile: hub (:443) and Space (:8446) go behind luminos-gate. DECISION 187.
import re, sys
s = open(sys.argv[1]).read()
SNIP = '''
# [CHANGE: cowork | 2026-11-13] DECISION 187 -- admin-only sites. luminos-gate (127.0.0.1:8101)
# answers /luminos-auth/* itself and is asked (forward_auth) before anything else is served.
# /fonts/* stays open so the sign-in page can use the house typeface; fonts reveal nothing.
(gated) {
	header {
		-Server
		X-Content-Type-Options "nosniff"
		Referrer-Policy "no-referrer"
	}
	handle /luminos-auth/* {
		reverse_proxy 127.0.0.1:8101
	}
	handle /fonts/* {
		reverse_proxy 127.0.0.1:{args[0]}
	}
	handle {
		forward_auth 127.0.0.1:8101 {
			uri /luminos-auth/check
			copy_headers X-Luminos-User
		}
		reverse_proxy 127.0.0.1:{args[0]}
	}
}
(gatedspace) {
	header {
		-Server
		X-Content-Type-Options "nosniff"
		Referrer-Policy "no-referrer"
	}
	handle /luminos-auth/* {
		reverse_proxy 127.0.0.1:8101
	}
	handle /fonts/* {
		reverse_proxy 127.0.0.1:8099
	}
	handle {
		route {
			forward_auth 127.0.0.1:8101 {
				uri /luminos-auth/check
				copy_headers X-Luminos-User
			}
			import spacetoken
			reverse_proxy 127.0.0.1:8099
		}
	}
}
'''
# insert snippets right after the (tsname) snippet
i = s.index("(tsname) {")
j = s.index("}\n", i) + 2
s = s[:j] + SNIP + s[j:]
n_hub = s.count("\timport proxy 8100\n")
s = s.replace("\timport proxy 8100\n", "\timport gated 8100\n")
pat = re.compile(r"\timport spacetoken\n\timport proxy 8099\n")
n_space = len(pat.findall(s))
s = pat.sub("\timport gatedspace\n", s)
if n_hub != 2 or n_space != 2:
    sys.exit("unexpected: hub=%d space=%d" % (n_hub, n_space))
open(sys.argv[2], "w").write(s)
print("hub blocks", n_hub, "space blocks", n_space)
