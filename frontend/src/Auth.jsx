import { useState } from "react";
import { supabase } from "./supabaseClient";

function Auth({ onAuthed }) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [mode, setMode] = useState("login");
    const [error, setError] = useState("");

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");

        try {
            const { data, error } =
                mode === "login"
                    ? await supabase.auth.signInWithPassword({ email, password })
                    : await supabase.auth.signUp({ email, password });

            if (error) {
                setError(error.message);
                return;
            }

            if (mode === "signup" && !data.session) {
                setError("Check your email to confirm your account, then log in.");
                return;
            }

            onAuthed();
        } catch (err) {
            setError("Something went wrong: " + err.message);
        }
    };

    return (
        <form onSubmit={handleSubmit} style={{ marginBottom: 20}}>
            <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required style={{ marginLeft: 8 }} />
            <button type="submit" style={{ marginLeft: 8 }}>{mode === "login" ? "Log in" : "Sign up"}</button>
            <button type="button" onClick={() => setMode(mode === "login" ? "signup" : "login")} style={{ marginLeft: 8 }}>
                {mode === "login" ? "Need an account?" : "Have an account?"}
            </button>
            {error && <p style={{ color: "red" }}>{error}</p>}
        </form>
    );
}

export default Auth;