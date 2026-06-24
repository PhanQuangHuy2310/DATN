import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useLogin, useRegister, useVerifyOtp, useResendOtp } from '@/features/auth';
import { useToast, Button } from '@/shared/ui';
import { getErrorMessage } from '@/shared/api';
import type { UserRole } from '@/shared/types';
import { AuthShell } from './AuthShell';
import { OtpInput } from './OtpInput';
import './AuthPage.css'; // Import file CSS tương ứng

const OTP_SECONDS = 300;

export const AuthPage = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const toast = useToast();

    const login = useLogin();
    const register = useRegister();
    const verify = useVerifyOtp();
    const resend = useResendOtp();

    // Default to login or register depending on the route path
    const isRegisterRoute = location.pathname === '/register';
    const [isActive, setIsActive] = useState(isRegisterRoute);
    
    // Check if we need to show OTP
    const [step, setStep] = useState<"form" | "otp">("form");

    // Login state
    const [loginEmail, setLoginEmail] = useState("");
    const [loginPassword, setLoginPassword] = useState("");
    const [loginRole, setLoginRole] = useState<UserRole>("TENANT");

    // Register state
    const [regForm, setRegForm] = useState({
        fullName: "",
        email: "",
        phone: "",
        password: "",
        role: "TENANT" as UserRole,
    });

    const setReg = <K extends keyof typeof regForm>(k: K, v: (typeof regForm)[K]) =>
        setRegForm((f) => ({ ...f, [k]: v }));

    const handleRegisterClick = () => {
        setIsActive(true);
        navigate('/register', { replace: true });
    };

    const handleLoginClick = () => {
        setIsActive(false);
        navigate('/login', { replace: true });
    };

    const from = (location.state as { from?: string } | null)?.from ?? "/";

    const handleLoginSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        login.mutate(
            { email: loginEmail, password: loginPassword, role: loginRole },
            {
                onSuccess: () => {
                    toast.success("Đăng nhập thành công!");
                    navigate(from, { replace: true });
                },
                onError: (err) => toast.error(getErrorMessage(err, "Sai tài khoản hoặc mật khẩu.")),
            }
        );
    };

    const handleRegisterSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        register.mutate(regForm, {
            onSuccess: () => {
                toast.success("Đã gửi mã OTP tới email của bạn.");
                setStep("otp");
            },
            onError: (err) => toast.error(getErrorMessage(err)),
        });
    };

    // --- OTP Step Logic ---
    const [code, setCode] = useState("");
    const [seconds, setSeconds] = useState(OTP_SECONDS);

    useEffect(() => {
        if (step !== "otp" || seconds <= 0) return;
        const id = window.setInterval(() => setSeconds((s) => s - 1), 1000);
        return () => window.clearInterval(id);
    }, [step, seconds]);

    const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
    const ss = String(seconds % 60).padStart(2, "0");

    const handleOtpSubmit = () => {
        if (code.length < 6) return;
        verify.mutate(
            { email: regForm.email, otpCode: code },
            {
                onSuccess: () => {
                    toast.success("Xác thực tài khoản thành công!");
                    navigate("/", { replace: true });
                },
                onError: (err) => toast.error(getErrorMessage(err, "Mã OTP không đúng.")),
            }
        );
    };

    const onResend = () =>
        resend.mutate(regForm.email, {
            onSuccess: () => {
                toast.success("Đã gửi lại mã OTP.");
                setSeconds(OTP_SECONDS);
                setCode("");
            },
            onError: (err) => toast.error(getErrorMessage(err)),
        });

    if (step === "otp") {
        return (
            <AuthShell
                title="Xác thực tài khoản"
                subtitle={`Nhập mã 6 chữ số đã gửi tới ${regForm.email}.`}
            >
                <div className="space-y-5">
                    <OtpInput value={code} onChange={setCode} />

                    <div className="text-center text-sm text-fog">
                        {seconds > 0 ? (
                            <span>
                                Mã hết hạn sau <span className="font-semibold text-ink">{mm}:{ss}</span>
                            </span>
                        ) : (
                            <button type="button" onClick={onResend} className="font-medium text-cobalt hover:underline" disabled={resend.isPending}>
                                Gửi lại mã OTP
                            </button>
                        )}
                    </div>

                    <Button block size="lg" onClick={handleOtpSubmit} loading={verify.isPending} disabled={code.length < 6}>
                        Xác nhận
                    </Button>
                </div>
            </AuthShell>
        );
    }

    return (
        <div className="auth-body">
            <div className={`container ${isActive ? 'active' : ''}`} id="container">
                {/* Màn hình Đăng Ký (Sign Up) */}
                <div className="form-container sign-up">
                    <form onSubmit={handleRegisterSubmit}>
                        <h1 style={{ marginTop: '10px' }}>Tạo Tài Khoản</h1>
                        <div className="role-group">
                            <input
                                type="radio"
                                id="role-tenant"
                                name="role"
                                checked={regForm.role === 'TENANT'}
                                onChange={() => setReg('role', 'TENANT')}
                            />
                            <label htmlFor="role-tenant">Khách thuê</label>
                            
                            <input
                                type="radio"
                                id="role-landlord"
                                name="role"
                                checked={regForm.role === 'LANDLORD'}
                                onChange={() => setReg('role', 'LANDLORD')}
                            />
                            <label htmlFor="role-landlord">Chủ trọ</label>
                        </div>
                        <input
                            type="text"
                            placeholder="Họ và tên"
                            value={regForm.fullName}
                            onChange={(e) => setReg('fullName', e.target.value)}
                            required
                        />
                        <input
                            type="email"
                            placeholder="Email"
                            value={regForm.email}
                            onChange={(e) => setReg('email', e.target.value)}
                            required
                        />
                        <input
                            type="text"
                            placeholder="Số điện thoại"
                            value={regForm.phone}
                            onChange={(e) => setReg('phone', e.target.value)}
                            required
                        />
                        <input
                            type="password"
                            placeholder="Mật khẩu (tối thiểu 8 ký tự)"
                            value={regForm.password}
                            onChange={(e) => setReg('password', e.target.value)}
                            minLength={8}
                            required
                        />
                        <button type="submit" disabled={register.isPending}>
                            {register.isPending ? 'Đang xử lý...' : 'Đăng Ký'}
                        </button>
                    </form>
                </div>

                {/* Màn hình Đăng Nhập (Sign In) */}
                <div className="form-container sign-in">
                    <form onSubmit={handleLoginSubmit}>
                        <h1>Đăng Nhập</h1>
                        <div className="social-icons">
                            <a href="#" className="icon"><i className="fa-brands fa-google"></i></a>
                            <a href="#" className="icon"><i className="fa-brands fa-facebook-f"></i></a>
                        </div>
                        <span>hoặc sử dụng tài khoản email của bạn</span>
                        <div className="role-group">
                            <input
                                type="radio"
                                id="login-role-tenant"
                                name="login-role"
                                checked={loginRole === 'TENANT'}
                                onChange={() => setLoginRole('TENANT')}
                            />
                            <label htmlFor="login-role-tenant">Khách thuê</label>
                            
                            <input
                                type="radio"
                                id="login-role-landlord"
                                name="login-role"
                                checked={loginRole === 'LANDLORD'}
                                onChange={() => setLoginRole('LANDLORD')}
                            />
                            <label htmlFor="login-role-landlord">Chủ trọ</label>
                        </div>
                        <input
                            type="email"
                            placeholder="Email"
                            value={loginEmail}
                            onChange={(e) => setLoginEmail(e.target.value)}
                            required
                        />
                        <input
                            type="password"
                            placeholder="Mật khẩu"
                            value={loginPassword}
                            onChange={(e) => setLoginPassword(e.target.value)}
                            required
                        />
                        <a href="#">Quên mật khẩu?</a>
                        <button type="submit" disabled={login.isPending}>
                            {login.isPending ? 'Đang xử lý...' : 'Đăng Nhập'}
                        </button>
                    </form>
                </div>

                {/* Khối hiệu ứng Toggle dịch chuyển */}
                <div className="toggle-container">
                    <div className="toggle">
                        <div className="toggle-panel toggle-left">
                            <h1>Chào mừng trở lại!</h1>
                            <p>Đăng nhập bằng thông tin cá nhân của bạn để sử dụng tất cả các tính năng của trang web</p>
                            <button type="button" className="ghost-btn" id="login" onClick={handleLoginClick}>
                                Đăng Nhập
                            </button>
                        </div>
                        <div className="toggle-panel toggle-right">
                            <h1>Xin chào!</h1>
                            <p>Đăng ký tài khoản để bắt đầu tìm hoặc đăng tin phòng trọ</p>
                            <button type="button" className="ghost-btn" id="register" onClick={handleRegisterClick}>
                                Đăng Ký
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
