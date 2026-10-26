#include "prefix_feedback/resource_evidence.h"

#include <algorithm>
#include <map>
#include <set>
#include <sstream>

namespace prefix_feedback::resource_evidence {
namespace {
std::string path(const Json& value) { return value.at("path").get<std::string>(); }
Json metadata(const Json& value) {
    require(value.at("size").get<std::size_t>() <= 8388608, "resource evidence metadata bound");
    check_pin(value);
    return read_json(path(value));
}
bool contains(const Json& values, const Json& value) {
    return std::find(values.begin(), values.end(), value) != values.end();
}
void within(const std::string& child, const std::string& root) {
    const fs::path item(child);
    const fs::path parent(root);
    const auto relative = item.lexically_relative(parent);
    require(item.is_absolute() && item.lexically_normal() == item && !relative.empty() &&
                    !relative.is_absolute() && *relative.begin() != "..",
            "resource evidence output root differs");
}
std::string clock(const Json& value) {
    auto text = value.get<std::string>();
    if (text.ends_with("+00:00")) {
        text = text.substr(0, text.size() - 6) + "Z";
    }
    require((text.size() == 20 || text.size() == 27) && text.at(4) == '-' &&
                    text.at(7) == '-' && text.at(10) == 'T' && text.at(13) == ':' &&
                    text.at(16) == ':' && text.back() == 'Z',
            "resource evidence UTC clock differs");
    if (text.size() == 20) {
        text.insert(19, ".000000");
    }
    require(text.at(19) == '.', "resource evidence fractional clock differs");
    return text;
}
std::string raw_clock(const Json& value) {
    auto text = read_text(path(value));
    require(!text.empty() && text.back() == '\n', "resource evidence raw clock newline differs");
    text.pop_back();
    return clock(text);
}
void historical(const Json& value) {
    require(value.at("historical_index_terminal") == false &&
                    value.at("historical_admission_requalified") == false &&
                    value.at("historical_index_controller_source_pin").is_null() &&
                    value.at("historical_index_controller_source_qualified") == false,
            "resource evidence historical gaps were requalified");
}
void pins(const Json& values) {
    require(values.is_array(), "resource evidence pin array required");
    std::set<std::string> seen;
    for (const auto& value : values) {
        require(seen.insert(path(value)).second, "resource evidence duplicate pin path");
        check_pin(value);
    }
}
void fai(const Json& reference, const Json& index, const Json& legacy) {
    std::istringstream input(read_text(path(index)));
    std::string line;
    Json names = Json::object();
    std::size_t total{};
    while (std::getline(input, line)) {
        std::istringstream row(line);
        std::vector<std::string> fields;
        std::string field;
        while (std::getline(row, field, '\t')) {
            fields.push_back(field);
        }
        require(fields.size() == 5 && !fields[0].empty() && !names.contains(fields[0]),
                "resource evidence malformed FAI");
        auto number = [&](std::size_t index_value) {
            const auto& text = fields.at(index_value);
            require(!text.empty() && text.find_first_not_of("0123456789") == std::string::npos,
                    "resource evidence unsigned FAI field required");
            return static_cast<std::size_t>(std::stoull(text));
        };
        const auto length = number(1);
        require(length > 0 && number(2) < reference.at("size").get<std::size_t>() &&
                        number(3) > 0 && number(3) <= number(4),
                "resource evidence FAI geometry differs");
        names[fields[0]] = length;
        total += length;
    }
    require(!names.empty() && names == legacy.at("contig_names_lengths") &&
                    names.size() == legacy.at("contigs").get<std::size_t>() &&
                    total == legacy.at("reference_bases").get<std::size_t>(),
            "resource evidence full contig map differs");
}
}
Trust frozen_trust() {
    const std::string root = "/home/jake/Projects/nanopore_basecaller-next-stock-compare";
    return {root,
            {{"path", root + "/tools/stock_feedback/resource_attestation.py"},
             {"size", 15909},
             {"sha256", "493f81f77b43a8397d81a054fff94bf811b372ccc4803e1c45160f0aed43cbef"}},
            {{"path", root + "/tools/stock_feedback/bounded.py"},
             {"size", 18293},
             {"sha256", "8adfc5a212061cfc079bb2e47cae12546c5d5bb9aba2adf0a6073e9d62710fc4"}},
            {{"path", root + "/tools/stock_feedback/resource-attestation-hg002-v1.json"},
             {"size", 5124},
             {"sha256", "07ee873412120209ede91d96c702466eefc07591f9bf9bfa4646bfc3fe233949"}},
            Json::array({{{"path", root + "/tools/stock_feedback/legacy.py"}, {"size", 15190},
                          {"sha256", "e18557d6d64c78d5f928173c9b5a2be35b5a05a70feafe9b365a0c2e4b9ba2f0"}},
                         {{"path", "/tmp/nanopore-frontier/private-raw-case/cpu-qualification-prep-v1/process_guard.py"}, {"size", 3443},
                          {"sha256", "dd90a7c50cd1b3044178e3ee248e7f5e948840496b1ad0cee3b99dadad6a14e9"}}})};
}
void validate(const Json& resources, const Json& evidence, const Trust& trust) {
    require(evidence.size() == 7 && evidence.at("schema") == "prefix-legacy-resource-evidence/1" &&
                    evidence.at("spec") == trust.spec,
            "resource evidence tag/trusted spec differs");
    const auto spec = metadata(evidence.at("spec"));
    const auto proof = metadata(evidence.at("attestation"));
    require(proof.at("schema") == "prefix-legacy-resource-attestation/1" &&
                    proof.at("complete") == true && proof.at("purpose") == "current-resource" &&
                    proof.at("source") == trust.verifier && proof.at("supervisor") == trust.supervisor,
            "resource evidence trusted verifier/purpose differs");
    require(spec.at("schema") == "prefix-legacy-resource-request/1" &&
                    spec.at("purpose") == "current-resource" &&
                    proof.at("resources") == spec.at("resources") &&
                    proof.at("tools") == spec.at("tools"),
            "resource evidence request map differs");
    check_pin(trust.verifier);
    check_pin(trust.supervisor);
    const auto& current = proof.at("resources");
    require(current.size() == 6 && current.at("mmi") == resources.at("reference_index") &&
                    current.at("reference") == resources.at("reference") &&
                    current.at("fai") == resources.at("reference_fai"),
            "resource evidence current resource relationship differs");
    // The exact, deduplicated admitted input closure below checks all six
    // resource bodies. Mapper/samtools also need current checks in this parser.
    for (const auto& key : {"mapper", "samtools"}) {
        check_pin(resources.at(key));
    }
    historical(proof);
    require(proof.at("current_resource_verification") == true &&
                    proof.at("new_index_built") == false && proof.at("new_fai_built") == false &&
                    proof.at("external_worker_and_outer_completion_required") == true &&
                    proof.at("checks") == Json{{"current_pins_verified", true}, {"legacy_custody_verified", true},
                                               {"stream_size_verified", true}, {"stream_digest_verified", true}},
            "resource evidence verification flags differ");
    const auto& legacy = proof.at("legacy");
    historical(legacy);
    require(legacy.at("registered_final_output") == current.at("mmi") &&
                    legacy.at("registered_compressed_input") == current.at("compressed") &&
                    legacy.at("registered_tool") == resources.at("mapper") &&
                    legacy.at("index_build") == spec.at("registries").at("index_built") &&
                    legacy.at("reference_registration") == spec.at("registries").at("reference_qualified") &&
                    legacy.at("index_argv") == spec.at("index_argv") &&
                    legacy.at("decompress_argv") == spec.at("decompress_argv") &&
                    legacy.at("fai").at("receipt") == spec.at("registries").at("fai_finish") &&
                    legacy.at("fai").at("argv") == Json::array({resources.at("samtools").at("path"), "faidx", "--fai-idx",
                                                                current.at("registered_fai").at("path"), current.at("reference").at("path")}) &&
                    spec.at("samtools_path").get<std::string>() == path(resources.at("samtools")),
            "resource evidence legacy resource relationship differs");
    const auto& index_argv = legacy.at("index_argv");
    const auto destination = std::find(index_argv.begin(), index_argv.end(), Json("-d"));
    require(index_argv.size() >= 4 && destination != index_argv.end() &&
                    destination + 1 != index_argv.end() &&
                    index_argv.front().get<std::string>() == path(resources.at("mapper")) &&
                    index_argv.back().get<std::string>() == path(current.at("compressed")),
            "resource evidence historical index argv differs");
    const auto old_output = (destination + 1)->get<std::string>();
    const auto old_dir = fs::path(path(legacy.at("index_raw").at("command.sh"))).parent_path();
    require(legacy.at("missing_now") == Json::array({old_output, (old_dir / "terminal.json").string(),
                                                     (old_dir / "outer-terminal.json").string()}),
            "resource evidence missing historical paths differ");
    for (const auto& key : {"fai", "registered_fai"}) {
        require(current.at(key).at("size") == current.at("publisher_fai").at("size") &&
                        current.at(key).at("sha256") == current.at("publisher_fai").at("sha256"),
                "resource evidence FAI aliases differ");
    }
    fai(current.at("reference"), current.at("fai"), legacy);
    const auto& stream = proof.at("stream");
    require(stream.at("bytes") == current.at("reference").at("size") &&
                    stream.at("sha256") == current.at("reference").at("sha256") &&
                    stream.at("exits") == Json{{"gzip", 0}, {"sha256", 0}},
            "resource evidence stream equivalence differs");
    const fs::path proof_root = fs::path(path(evidence.at("attestation"))).parent_path();
    within(proof_root.string(), trust.root);
    require(path(evidence.at("attestation")) == (proof_root / "complete.json").string(),
            "resource evidence attestation filename differs");
    const auto terminal = metadata(proof.at("terminal"));
    require(path(proof.at("terminal")) == (proof_root / "terminal.json").string() &&
                    terminal.at("error").is_null() && terminal.at("phase") == "equivalence" &&
                    terminal.at("projection_pending") == true && terminal.at("stream") == stream &&
                    terminal.at("checks") == proof.at("checks"),
            "resource evidence verifier terminal differs");
    require(proof.at("admission") == evidence.at("admission"), "resource evidence admission pin differs");
    const auto admission = metadata(evidence.at("admission"));
    const auto worker = metadata(evidence.at("worker_complete"));
    const auto worker_terminal = metadata(worker.at("terminal"));
    const fs::path worker_root = fs::path(path(evidence.at("worker_complete"))).parent_path();
    within(worker_root.string(), trust.root);
    require(path(evidence.at("worker_complete")) == (worker_root / "complete.json").string(),
            "resource evidence worker filename differs");
    require(admission.at("schema") == "bounded-command/1" && admission.at("root") == trust.root &&
                    admission.at("cwd") == trust.root && admission.at("roles").at("unit") == "F4/resource-attestation" &&
                    admission.at("argv") == Json::array({"/home/jake/.local/bin/uv", "run", "--project",
                        "/home/jake/Projects/nanopore_basecaller-retrieval", "--no-sync", "python", path(trust.verifier),
                        "verify", "--spec", path(evidence.at("spec")), "--grant", path(evidence.at("admission")), "--output", proof_root.string()}),
            "resource evidence admitted role/argv differs");
    require(admission.at("profile") == "engineering" && admission.at("cpus") == 2 &&
                    admission.at("wall_seconds").get<std::size_t>() <= 300 && admission.at("wall_seconds").get<std::size_t>() > 0 &&
                    admission.at("memory_bytes") == 4294967296ULL && admission.at("address_space_bytes") == 8589934592ULL &&
                    admission.at("swap_bytes") == 0 && admission.at("growth_bytes") == 104857600 &&
                    admission.at("aggregate_bytes") == 4294967296ULL && admission.at("reserve_bytes") == 32212254720ULL,
            "resource evidence admitted caps differ");
    std::set<std::string> roots;
    for (const auto& root : admission.at("output_roots")) {
        const auto value = root.get<std::string>();
        within(value, trust.root);
        require(roots.insert(value).second, "resource evidence duplicate admitted output root");
    }
    require(roots.contains(worker_root.parent_path().string()) &&
                    std::any_of(roots.begin(), roots.end(), [&](const auto& root) {
                        const auto relative = proof_root.lexically_relative(root);
                        return !relative.empty() && !relative.is_absolute() && *relative.begin() != "..";
                    }),
            "resource evidence admitted output root coverage differs");
    pins(admission.at("source_pins"));
    pins(admission.at("input_pins"));
    require(contains(admission.at("source_pins"), trust.verifier) &&
                    contains(admission.at("source_pins"), trust.supervisor),
            "resource evidence admitted source membership differs");
    for (const auto& source : trust.required_sources) {
        require(contains(admission.at("source_pins"), source), "resource evidence imported source not admitted");
    }
    for (const auto& tool : proof.at("tools")) {
        require(contains(admission.at("source_pins"), tool), "resource evidence native tool not admitted");
    }
    const auto& input_roles = admission.at("roles").at("inputs");
    std::set<std::size_t> indices;
    for (const auto& index : input_roles) {
        indices.insert(index.get<std::size_t>());
    }
    require(input_roles.size() == admission.at("input_pins").size() && indices.size() == input_roles.size(),
            "resource evidence input role census differs");
    for (std::size_t index = 0; index < input_roles.size(); ++index) {
        require(indices.contains(index), "resource evidence input role index differs");
    }
    auto role = [&](const std::string& name, const Json& value) {
        require(admission.at("input_pins").at(input_roles.at(name).get<std::size_t>()) == value,
                "resource evidence semantic input role differs");
    };
    role("resource-spec", evidence.at("spec"));
    for (const auto& entry : current.items()) { role("resource-" + entry.key(), entry.value()); }
    for (const auto& entry : spec.at("registries").items()) {
        auto name = entry.key();
        std::replace(name.begin(), name.end(), '_', '-');
        role("registry-" + name, entry.value());
    }
    std::map<std::string, Json> expected_inputs;
    auto expect_input = [&](const Json& value) {
        const auto [entry, inserted] = expected_inputs.emplace(path(value), value);
        require(inserted || entry->second == value, "resource evidence conflicting input aliases");
    };
    expect_input(evidence.at("spec"));
    for (const auto& value : current) { expect_input(value); }
    for (const auto& value : spec.at("registries")) { expect_input(value); }
    require(legacy.at("decompress_raw").at("stdout") == current.at("reference"),
            "resource evidence decompressor output differs");
    for (const auto& stage : {"index", "decompress", "faidx"}) {
        const auto& values = std::string(stage) == "faidx" ? legacy.at("fai").at("raw")
                            : legacy.at(std::string(stage) + "_raw");
        require(values.size() == 8, "resource evidence historical raw census differs");
        for (const auto& name : {"command.sh", "cwd.txt", "start.txt", "end.txt", "exit-status.txt", "stdout", "stderr", "time.txt"}) {
            const auto& value = values.at(name);
            expect_input(value);
            if (std::string(stage) != "decompress" || std::string(name) != "stdout") {
                auto name_role = std::string(name);
                std::replace(name_role.begin(), name_role.end(), '.', '-');
                role(std::string(stage) + "-" + name_role, value);
            }
        }
    }
    require(expected_inputs.size() == admission.at("input_pins").size(),
            "resource evidence exact input census differs");
    for (const auto& value : admission.at("input_pins")) {
        require(expected_inputs.at(path(value)) == value, "resource evidence exact input tuple differs");
    }
    require(worker.at("schema") == "bounded-command-result/1" && worker.at("complete") == true &&
                    worker.at("admission") == evidence.at("admission") &&
                    path(worker.at("terminal")) == (worker_root / "terminal.json").string() &&
                    worker_terminal.at("exit") == 0 && worker_terminal.at("exit_known") == true &&
                    worker_terminal.at("error").is_null() && worker_terminal.at("cleanup").at("terminal") == true,
            "resource evidence worker completion differs");
    std::map<std::string, Json> raw;
    for (const auto& item : worker.at("raw")) {
        check_pin(item);
        require(raw.emplace(fs::path(path(item)).filename().string(), item).second &&
                        fs::path(path(item)).parent_path() == worker_root,
                "resource evidence worker raw layout differs");
    }
    require(raw.size() == 8, "resource evidence worker raw census differs");
    const auto command = metadata(raw.at("command.json"));
    for (const auto& key : {"argv", "cwd", "env", "source_pins", "input_pins", "roles"}) {
        require(command.at(key) == admission.at(key), "resource evidence worker command tuple differs");
    }
    require(read_text(path(raw.at("cwd.txt"))) == trust.root + "\n" &&
                    read_text(path(raw.at("exit-status.txt"))) == "0\n" &&
                    raw_clock(raw.at("start.txt")) == clock(worker_terminal.at("start")) &&
                    raw_clock(raw.at("end.txt")) == clock(worker_terminal.at("end")) &&
                    read_text(path(raw.at("time.txt"))).find("\tExit status: 0\n") != std::string::npos,
            "resource evidence worker raw status differs");
    Json linked = Json::array({evidence.at("attestation"), proof.at("terminal")});
    for (const auto& name : {"gzip", "sha256"}) {
        const auto& values = stream.at("raw").at(name);
        const std::vector<std::string> files = std::string(name) == "gzip"
            ? std::vector<std::string>{"command.json", "cwd.txt", "start.txt", "end.txt", "exit-status.txt", "time.txt", "stderr", "terminal.json"}
            : std::vector<std::string>{"command.json", "cwd.txt", "start.txt", "end.txt", "exit-status.txt", "time.txt", "stderr", "terminal.json", "stdout"};
        require(values.size() == files.size(), "resource evidence native raw census differs");
        for (std::size_t index = 0; index < files.size(); ++index) {
            require(path(values.at(index)) == (proof_root / name / files[index]).string(), "resource evidence native raw layout differs");
            check_pin(values.at(index));
            linked.push_back(values.at(index));
        }
        const auto native_terminal = metadata(values.at(7));
        require(values.at(7) == stream.at("terminal_pins").at(name) &&
                        native_terminal.at("recorder_exit") == 0 && native_terminal.at("exit_known") == true &&
                        native_terminal.at("error").is_null() && native_terminal.at("cleanup").at("terminal") == true &&
                        native_terminal.at("cleanup") == stream.at("cleanup").at(name) &&
                        native_terminal.at("stdout_mode") == (std::string(name) == "gzip" ? "streamed-and-counted" : "digest-only") &&
                        clock(terminal.at("start")) <= clock(native_terminal.at("start")) &&
                        clock(native_terminal.at("start")) <= clock(native_terminal.at("end")) &&
                        clock(native_terminal.at("end")) <= clock(terminal.at("end")),
                "resource evidence native terminal differs");
        const auto native_command = metadata(values.at(0));
        const auto native_argv = std::string(name) == "gzip"
            ? Json::array({proof.at("tools").at("gzip").at("path"), "-cd", "--", current.at("compressed").at("path")})
            : Json::array({proof.at("tools").at("sha256sum").at("path")});
        auto wrapped = Json::array({proof.at("tools").at("time").at("path"), "-v", "-o", (proof_root / name / "time.txt").string(), "--"});
        for (const auto& argument : native_argv) { wrapped.push_back(argument); }
        require(native_command.at("native_argv") == native_argv && native_command.at("argv") == wrapped &&
                        native_command.at("cwd") == trust.root && native_command.at("env") == Json{{"LC_ALL", "C"}} &&
                        native_command.at("tool") == proof.at("tools").at(std::string(name) == "gzip" ? "gzip" : "sha256sum") &&
                        read_text(path(values.at(1))) == trust.root + "\n" &&
                        raw_clock(values.at(2)) == clock(native_terminal.at("start")) &&
                        raw_clock(values.at(3)) == clock(native_terminal.at("end")) &&
                        read_text(path(values.at(4))) == "0\n" &&
                        read_text(path(values.at(5))).find("\tExit status: 0\n") != std::string::npos,
                "resource evidence native command/status differs");
        if (std::string(name) == "sha256") {
            require(read_text(path(values.at(8))) == current.at("reference").at("sha256").get<std::string>() + "  -\n",
                    "resource evidence native digest stdout differs");
        }
    }
    require(worker.at("linked") == linked, "resource evidence worker output pins differ");
    Json expected_paths = Json::array();
    Json output_roles = Json::object();
    for (std::size_t index = 0; index < linked.size(); ++index) {
        expected_paths.push_back(path(linked.at(index)));
        output_roles["proof-" + std::to_string(index)] = path(linked.at(index));
    }
    require(admission.at("expected_files") == expected_paths && admission.at("roles").at("outputs") == output_roles,
            "resource evidence admitted outputs differ");
    const auto outer = metadata(evidence.at("outer_terminal"));
    const auto outer_command = metadata(evidence.at("outer_command"));
    require(path(evidence.at("outer_terminal")) == (worker_root / "outer-terminal.json").string() &&
                    path(evidence.at("outer_command")) == (worker_root / "outer-command.json").string() &&
                    outer.at("exit") == 0 && outer.at("error").is_null() && outer.at("worker_complete") == true &&
                    outer.at("missing_worker_records").empty() && outer.at("empty_before_unlock") == true &&
                    outer.at("proof").at("launcher_group_empty") == true &&
                    outer.at("proof").at("service_cgroup_empty") == true && outer.at("proof").at("failures").empty(),
            "resource evidence outer completion differs");
    const auto& outer_argv = outer_command.at("argv");
    const auto separator = std::find(outer_argv.begin(), outer_argv.end(), Json("--"));
    require(outer_command.at("cwd") == trust.root && separator != outer_argv.end() &&
                    outer_argv.end() - separator == 10 &&
                    Json(separator + 2, outer_argv.end()) == Json::array({path(trust.supervisor), "worker", "--request", path(evidence.at("admission")),
                        "--request-sha256", evidence.at("admission").at("sha256"), "--output", worker_root.string()}),
            "resource evidence outer request binding differs");
    const auto interpreter = fs::canonical((separator + 1)->get<std::string>()).string();
    require(std::any_of(admission.at("source_pins").begin(), admission.at("source_pins").end(),
                        [&](const Json& item) { return path(item) == interpreter; }),
            "resource evidence outer interpreter not admitted");
    const auto unit = "feedback-next-" + admission.at("id").get<std::string>() + ".service";
    require(contains(outer_argv, "--unit=" + unit) && contains(outer_argv, "--working-directory=" + trust.root) &&
                    contains(outer_argv, "--property=Type=exec") && contains(outer_argv, "--property=ExitType=cgroup") &&
                    contains(outer_argv, "--property=KillMode=control-group") && contains(outer_argv, "--property=CPUQuota=200%") &&
                    contains(outer_argv, "--property=MemoryMax=" + std::to_string(admission.at("memory_bytes").get<std::size_t>())) &&
                    contains(outer_argv, "--property=LimitAS=" + std::to_string(admission.at("address_space_bytes").get<std::size_t>())) &&
                    contains(outer_argv, "--property=MemorySwapMax=0") &&
                    outer.at("proof").at("cgroup").get<std::string>().ends_with("/" + unit),
            "resource evidence outer unit/caps differ");
    std::string runtime;
    for (const auto& value : outer_argv) {
        const auto argument = value.get<std::string>();
        if (argument.starts_with("--property=RuntimeMaxSec=")) {
            require(runtime.empty(), "resource evidence duplicate outer runtime");
            runtime = argument;
        }
    }
    require(runtime.size() > 25 && runtime.back() == 's', "resource evidence outer runtime missing");
    const auto seconds = runtime.substr(25, runtime.size() - 26);
    require(!seconds.empty() && seconds.find_first_not_of("0123456789") == std::string::npos &&
                    std::stoull(seconds) > 0 && std::stoull(seconds) <= admission.at("wall_seconds").get<std::size_t>(),
            "resource evidence outer runtime differs");
    auto expected_outer = Json::array({"/usr/bin/systemd-run", "--user", "--wait", "--pipe", "--unit=" + unit,
        "--working-directory=" + trust.root, "--property=Type=exec", "--property=ExitType=cgroup",
        "--property=KillMode=control-group", "--property=CollectMode=inactive", "--property=SendSIGKILL=yes",
        "--property=FinalKillSignal=SIGKILL", "--property=TimeoutStopSec=1s", runtime, "--property=Restart=no",
        "--property=Slice=app.slice", "--property=CPUQuota=200%", "--property=MemoryMax=4294967296",
        "--property=MemorySwapMax=0", "--property=LimitAS=8589934592"});
    for (const auto& entry : admission.at("env").items()) {
        expected_outer.push_back("--setenv=" + entry.key() + "=" + entry.value().get<std::string>());
    }
    for (auto item = separator; item != outer_argv.end(); ++item) { expected_outer.push_back(*item); }
    require(outer_argv == expected_outer, "resource evidence exact outer command differs");
    require(clock(admission.at("not_before_utc")) <= clock(outer_command.at("start")) &&
                    clock(outer_command.at("start")) <= clock(worker_terminal.at("start")) &&
                    clock(worker_terminal.at("start")) <= clock(terminal.at("start")) &&
                    clock(terminal.at("start")) <= clock(terminal.at("end")) &&
                    clock(terminal.at("end")) <= clock(worker_terminal.at("end")) &&
                    clock(worker_terminal.at("end")) <= clock(outer.at("end")) &&
                    clock(outer.at("end")) <= clock(admission.at("expires_utc")),
            "resource evidence admission/worker clocks differ");
}
}
