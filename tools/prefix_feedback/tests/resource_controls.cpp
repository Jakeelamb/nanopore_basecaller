#include "prefix_feedback/resource_evidence.h"

#include <unistd.h>

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iostream>

namespace prefix_feedback {
namespace {
struct ResourceFixture {
    fs::path root;
    fs::path proof_root;
    fs::path worker_root;
    resource_evidence::Trust trust;
    Json resources;
    Json spec;
    Json proof;
    Json admission;
    Json worker_terminal;
    Json outer;
    Json evidence;
    std::string suffix_hash;
    bool foreign_worker_command{};
    static constexpr const char* started = "2026-10-26T23:00:01.000000+00:00";
    static constexpr const char* ended = "2026-10-26T23:00:02.000000+00:00";
    Json literal(const fs::path& file, const std::string& bytes) {
        fresh_bytes(file, bytes);
        return pin(file);
    }
    Json json(const fs::path& file, const Json& value) {
        fresh(file, value);
        return pin(file);
    }
    ResourceFixture() {
        static std::size_t serial{};
        const auto* temporary = std::getenv("TMPDIR");
        require(temporary != nullptr && *temporary != '\0', "resource fixture TMPDIR required");
        const auto owned = fs::canonical(fs::path(source_witness().at("root").get<std::string>()) /
                                         "results/prefix-feedback");
        const fs::path base(temporary);
        const auto relative = base.lexically_relative(owned);
        require(base.is_absolute() && fs::canonical(base) == base && !relative.empty() &&
                        !relative.is_absolute() && *relative.begin() != "..",
                "resource fixture outside monitored results");
        root = base /
               ("resource-control-" + std::to_string(::getpid()) + "-" + std::to_string(serial++));
        require(fs::create_directory(root), "fresh resource fixture required");
        proof_root = root / "proof";
        worker_root = root / "worker";
        fs::create_directory(proof_root);
        fs::create_directory(worker_root);
        trust.root = root.string();
        trust.verifier =
                literal(root / "verifier.literal", "synthetic verifier identity; not executed\n");
        trust.supervisor = literal(root / "supervisor.literal",
                                   "synthetic supervisor identity; not executed\n");
        trust.required_sources =
                Json::array({literal(root / "legacy.literal", "synthetic imported source\n"),
                             literal(root / "guard.literal", "synthetic guard source\n")});
        const auto interpreter =
                literal(root / "interpreter.literal", "synthetic interpreter; not executed\n");
        resources = {{"mapper", literal(root / "mapper.literal", "tiny current mapper\n")},
                     {"reference_index", literal(root / "index.literal", "tiny final MMI\n")},
                     {"reference", literal(root / "reference.fasta", ">chr1\nAAAA\n")},
                     {"reference_fai", literal(root / "reference.fai", "chr1\t4\t6\t4\t5\n")},
                     {"samtools", literal(root / "samtools.literal", "tiny current samtools\n")},
                     {"producer_sources", Json::array({trust.verifier})}};
        Json current{{"compressed", literal(root / "compressed.literal",
                                            "tiny compressed identity; not decompressed\n")},
                     {"reference", resources.at("reference")},
                     {"mmi", resources.at("reference_index")},
                     {"fai", resources.at("reference_fai")},
                     {"publisher_fai", literal(root / "publisher.fai", "chr1\t4\t6\t4\t5\n")},
                     {"registered_fai", literal(root / "registered.fai", "chr1\t4\t6\t4\t5\n")}};
        Json tools = Json::object();
        for (const auto& name : {"gzip", "sha256sum", "time"}) {
            tools[name] = literal(root / (std::string(name) + ".literal"),
                                  std::string("tiny tool ") + name + "\n");
        }
        Json registries = Json::object();
        for (const auto& name :
             {"index_built", "index_qualified", "reference_qualified", "fai_finish"}) {
            registries[name] = json(root / (std::string(name) + ".json"), {{"fixture", name}});
        }
        const auto index_argv = Json::array({resources.at("mapper").at("path"), "-d",
                                             (root / "missing-temporary.mmi").string(),
                                             current.at("compressed").at("path")});
        const auto decompress_argv =
                Json::array({"gzip", "-cd", current.at("compressed").at("path")});
        Json historical_raw = Json::object();
        for (const auto& stage : {"index_raw", "decompress_raw", "fai_raw"}) {
            const auto directory = root / stage;
            fs::create_directory(directory);
            historical_raw[stage] = Json::object();
            for (const auto& name : {"command.sh", "cwd.txt", "start.txt", "end.txt",
                                     "exit-status.txt", "stdout", "stderr", "time.txt"}) {
                historical_raw[stage][name] =
                        literal(directory / name, "synthetic retained old metadata\n");
            }
        }
        historical_raw["decompress_raw"]["stdout"] = current.at("reference");
        spec = {{"schema", "prefix-legacy-resource-request/1"},
                {"purpose", "current-resource"},
                {"resources", current},
                {"tools", tools},
                {"registries", registries},
                {"index_argv", index_argv},
                {"decompress_argv", decompress_argv},
                {"samtools_path", resources.at("samtools").at("path")}};
        trust.spec = json(root / "spec.json", spec);
        auto history = Json{
                {"registered_final_output", current.at("mmi")},
                {"registered_compressed_input", current.at("compressed")},
                {"registered_tool", resources.at("mapper")},
                {"index_build", registries.at("index_built")},
                {"reference_registration", registries.at("reference_qualified")},
                {"index_argv", index_argv},
                {"decompress_argv", decompress_argv},
                {"index_raw", historical_raw.at("index_raw")},
                {"decompress_raw", historical_raw.at("decompress_raw")},
                {"fai",
                 {{"receipt", registries.at("fai_finish")},
                  {"raw", historical_raw.at("fai_raw")},
                  {"argv", Json::array({resources.at("samtools").at("path"), "faidx", "--fai-idx",
                                        current.at("registered_fai").at("path"),
                                        current.at("reference").at("path")})}}},
                {"contig_names_lengths", {{"chr1", 4}}},
                {"contigs", 1},
                {"reference_bases", 4},
                {"missing_now", Json::array({(root / "missing-temporary.mmi").string(),
                                             (root / "index_raw/terminal.json").string(),
                                             (root / "index_raw/outer-terminal.json").string()})}};
        for (const auto& key : {"historical_index_terminal", "historical_admission_requalified",
                                "historical_index_controller_source_qualified"}) {
            history[key] = false;
        }
        history["historical_index_controller_source_pin"] = nullptr;
        proof = {{"schema", "prefix-legacy-resource-attestation/1"},
                 {"complete", true},
                 {"purpose", "current-resource"},
                 {"resources", current},
                 {"legacy", history},
                 {"source", trust.verifier},
                 {"supervisor", trust.supervisor},
                 {"tools", tools},
                 {"checks",
                  {{"current_pins_verified", true},
                   {"legacy_custody_verified", true},
                   {"stream_size_verified", true},
                   {"stream_digest_verified", true}}},
                 {"current_resource_verification", true},
                 {"historical_index_terminal", false},
                 {"historical_admission_requalified", false},
                 {"historical_index_controller_source_pin", nullptr},
                 {"historical_index_controller_source_qualified", false},
                 {"new_index_built", false},
                 {"new_fai_built", false},
                 {"external_worker_and_outer_completion_required", true},
                 {"stream",
                  {{"bytes", current.at("reference").at("size")},
                   {"sha256", current.at("reference").at("sha256")},
                   {"exits", {{"gzip", 0}, {"sha256", 0}}}}}};
        Json source_pins = Json::array({trust.verifier, trust.supervisor, interpreter});
        for (const auto& source : trust.required_sources) {
            source_pins.push_back(source);
        }
        for (const auto& tool : tools) {
            source_pins.push_back(tool);
        }
        Json inputs = Json::array();
        Json input_roles = Json::object();
        auto add = [&](const std::string& role, const Json& value) {
            input_roles[role] = inputs.size();
            inputs.push_back(value);
        };
        add("resource-spec", trust.spec);
        add("resource-compressed", current.at("compressed"));
        add("resource-reference", current.at("reference"));
        add("resource-mmi", current.at("mmi"));
        add("resource-fai", current.at("fai"));
        add("resource-publisher-fai", current.at("publisher_fai"));
        add("resource-registered-fai", current.at("registered_fai"));
        for (const auto& entry : registries.items()) {
            auto role = entry.key();
            std::replace(role.begin(), role.end(), '_', '-');
            add("registry-" + role, entry.value());
        }
        for (const auto& stage : historical_raw.items()) {
            for (const auto& entry : stage.value().items()) {
                if (stage.key() == "decompress_raw" && entry.key() == "stdout") {
                    continue;
                }
                const auto name = stage.key() == "index_raw"        ? "index"
                                  : stage.key() == "decompress_raw" ? "decompress"
                                                                    : "faidx";
                auto raw_name = entry.key();
                std::replace(raw_name.begin(), raw_name.end(), '.', '-');
                add(std::string(name) + "-" + raw_name, entry.value());
            }
        }
        admission = {{"schema", "bounded-command/1"},
                     {"id", "tiny-resource"},
                     {"root", trust.root},
                     {"cwd", trust.root},
                     {"argv", Json::array({"/home/jake/.local/bin/uv", "run", "--project",
                                           "/home/jake/Projects/nanopore_basecaller-retrieval",
                                           "--no-sync", "python", trust.verifier.at("path"),
                                           "verify", "--spec", trust.spec.at("path"), "--grant",
                                           (root / "admission.json").string(), "--output",
                                           proof_root.string()})},
                     {"source_pins", source_pins},
                     {"input_pins", inputs},
                     {"env", {{"LC_ALL", "C"}}},
                     {"roles", {{"unit", "F4/resource-attestation"}, {"inputs", input_roles}}},
                     {"memory_bytes", 4294967296ULL},
                     {"address_space_bytes", 8589934592ULL},
                     {"output_roots", Json::array({root.string()})},
                     {"profile", "engineering"},
                     {"cpus", 2},
                     {"wall_seconds", 300},
                     {"swap_bytes", 0},
                     {"growth_bytes", 104857600},
                     {"aggregate_bytes", 4294967296ULL},
                     {"reserve_bytes", 32212254720ULL},
                     {"not_before_utc", "2026-10-26T23:00:00.000000+00:00"},
                     {"expires_utc", "2026-10-26T23:00:03.000000+00:00"}};
        worker_terminal = {{"start", started}, {"end", ended},
                           {"exit", 0},        {"exit_known", true},
                           {"error", nullptr}, {"cleanup", {{"terminal", true}}}};
        outer = {{"end", ended},
                 {"exit", 0},
                 {"error", nullptr},
                 {"worker_complete", true},
                 {"missing_worker_records", Json::array()},
                 {"empty_before_unlock", true},
                 {"proof",
                  {{"launcher_group_empty", true},
                   {"service_cgroup_empty", true},
                   {"failures", Json::array()},
                   {"cgroup", "/synthetic/feedback-next-tiny-resource.service"}}}};
    }
    void seal() {
        Json linked_paths = Json::array(
                {(proof_root / "complete.json").string(), (proof_root / "terminal.json").string()});
        for (const auto& name : {"gzip", "sha256"}) {
            const auto directory = proof_root / name;
            fs::create_directory(directory);
            const auto tool = std::string(name) == "gzip" ? "gzip" : "sha256sum";
            const auto native =
                    std::string(name) == "gzip"
                            ? Json::array({proof.at("tools").at(tool).at("path"), "-cd", "--",
                                           proof.at("resources").at("compressed").at("path")})
                            : Json::array({proof.at("tools").at(tool).at("path")});
            auto wrapped = Json::array({proof.at("tools").at("time").at("path"), "-v", "-o",
                                        (directory / "time.txt").string(), "--"});
            for (const auto& arg : native) {
                wrapped.push_back(arg);
            }
            const auto cleanup = Json{{"terminal", true}};
            Json raw = Json::array(
                    {json(directory / "command.json", {{"native_argv", native},
                                                       {"argv", wrapped},
                                                       {"cwd", trust.root},
                                                       {"env", {{"LC_ALL", "C"}}},
                                                       {"tool", proof.at("tools").at(tool)}}),
                     literal(directory / "cwd.txt", trust.root + "\n"),
                     literal(directory / "start.txt", std::string(started) + "\n"),
                     literal(directory / "end.txt", std::string(ended) + "\n"),
                     literal(directory / "exit-status.txt", "0\n"),
                     literal(directory / "time.txt", "\tExit status: 0\n"),
                     literal(directory / "stderr", ""),
                     json(directory / "terminal.json",
                          {{"start", started},
                           {"end", ended},
                           {"recorder_exit", 0},
                           {"exit_known", true},
                           {"error", nullptr},
                           {"cleanup", cleanup},
                           {"stdout_mode", std::string(name) == "gzip" ? "streamed-and-counted"
                                                                       : "digest-only"}})});
            if (std::string(name) == "sha256") {
                raw.push_back(literal(
                        directory / "stdout",
                        proof.at("resources").at("reference").at("sha256").get<std::string>() +
                                "  -\n"));
            }
            proof["stream"]["raw"][name] = raw;
            proof["stream"]["cleanup"][name] = cleanup;
            proof["stream"]["terminal_pins"][name] = raw.at(7);
            for (const auto& value : raw) {
                linked_paths.push_back(value.at("path"));
            }
        }
        admission["expected_files"] = linked_paths;
        for (std::size_t index = 0; index < linked_paths.size(); ++index) {
            admission["roles"]["outputs"]["proof-" + std::to_string(index)] =
                    linked_paths.at(index);
        }
        evidence = {{"schema", "prefix-legacy-resource-evidence/1"},
                    {"spec", trust.spec},
                    {"admission", json(root / "admission.json", admission)}};
        proof["admission"] = evidence.at("admission");
        proof["terminal"] = json(proof_root / "terminal.json", {{"start", started},
                                                                {"end", ended},
                                                                {"error", nullptr},
                                                                {"phase", "equivalence"},
                                                                {"projection_pending", true},
                                                                {"stream", proof.at("stream")},
                                                                {"checks", proof.at("checks")}});
        evidence["attestation"] = json(proof_root / "complete.json", proof);
        Json linked = Json::array({evidence.at("attestation"), proof.at("terminal")});
        for (const auto& name : {"gzip", "sha256"}) {
            for (const auto& value : proof.at("stream").at("raw").at(name)) {
                linked.push_back(value);
            }
        }
        Json command;
        for (const auto& key : {"argv", "cwd", "env", "source_pins", "input_pins", "roles"}) {
            command[key] = admission.at(key);
        }
        if (foreign_worker_command) {
            command["env"]["FOREIGN"] = "1";
        }
        const auto raw = Json::array(
                {json(worker_root / "command.json", command),
                 literal(worker_root / "cwd.txt", trust.root + "\n"),
                 literal(worker_root / "start.txt", std::string(started) + "\n"),
                 literal(worker_root / "end.txt", std::string(ended) + "\n"),
                 literal(worker_root / "exit-status.txt", "0\n"),
                 literal(worker_root / "stdout", ""), literal(worker_root / "stderr", ""),
                 literal(worker_root / "time.txt", "\tExit status: 0\n")});
        evidence["worker_complete"] =
                json(worker_root / "complete.json",
                     {{"schema", "bounded-command-result/1"},
                      {"complete", true},
                      {"admission", evidence.at("admission")},
                      {"linked", linked},
                      {"raw", raw},
                      {"terminal", json(worker_root / "terminal.json", worker_terminal)}});
        auto outer_argv = Json::array(
                {"/usr/bin/systemd-run",
                 "--user",
                 "--wait",
                 "--pipe",
                 "--unit=feedback-next-tiny-resource.service",
                 "--working-directory=" + trust.root,
                 "--property=Type=exec",
                 "--property=ExitType=cgroup",
                 "--property=KillMode=control-group",
                 "--property=CollectMode=inactive",
                 "--property=SendSIGKILL=yes",
                 "--property=FinalKillSignal=SIGKILL",
                 "--property=TimeoutStopSec=1s",
                 "--property=RuntimeMaxSec=298s",
                 "--property=Restart=no",
                 "--property=Slice=app.slice",
                 "--property=CPUQuota=200%",
                 "--property=MemoryMax=4294967296",
                 "--property=MemorySwapMax=0",
                 "--property=LimitAS=8589934592",
                 "--setenv=LC_ALL=C",
                 "--",
                 admission.at("source_pins").at(2).at("path"),
                 trust.supervisor.at("path"),
                 "worker",
                 "--request",
                 evidence.at("admission").at("path"),
                 "--request-sha256",
                 suffix_hash.empty() ? evidence.at("admission").at("sha256").get<std::string>()
                                     : suffix_hash,
                 "--output",
                 worker_root.string()});
        evidence["outer_command"] =
                json(worker_root / "outer-command.json",
                     {{"argv", outer_argv}, {"cwd", trust.root}, {"start", started}});
        evidence["outer_terminal"] = json(worker_root / "outer-terminal.json", outer);
        resources["index_provenance"] = json(root / "evidence.json", evidence);
        const auto retained =
                json(root / "case.json",
                     {{"kind", "synthetic-parser-fixture-not-execution-authorization"},
                      {"evidence", evidence},
                      {"resources", resources}});
        std::cout << Json{{"resource_case", retained}, {"retained", true}, {"synthetic_only", true}}
                             .dump()
                  << '\n';
    }
    void validate() const { resource_evidence::validate(resources, evidence, trust); }
};
void rejection(const std::function<void()>& action, const std::string& expected) {
    std::string error;
    try {
        action();
    } catch (const std::exception& caught) {
        error = caught.what();
    }
    require(error.find(expected) != std::string::npos &&
                    error.find("source-root") == std::string::npos,
            "resource control missed intended guard: " + expected + ": " + error);
    std::cout << Json{{"resource_rejection", expected}, {"actual_error", error}}.dump() << '\n';
}
}
std::size_t resource_controls() {
    ResourceFixture positive;
    positive.seal();
    positive.validate();
    std::cout << "PASS resource-proof-complete-tiny-custody-positive\n";
    auto broken = positive.evidence;
    broken["attestation"]["sha256"] = std::string(64, 'f');
    positive.json(positive.root / "broken-proof-pin.json", broken);
    rejection([&] { resource_evidence::validate(positive.resources, broken, positive.trust); },
              "consumed input pin differs");
    const auto manifest =
            positive.json(positive.root / "manifest.json", {{"schema", "prefix-resources/1"},
                                                            {"plan_sha256", std::string(64, 'a')},
                                                            {"resources", positive.resources}});
    rejection([&] { validate_resources(manifest, std::string(64, 'a')); },
              "resource evidence tag/trusted spec differs");
    std::cout << "PASS resource-proof-root-pin-and-production-trust-boundary\n";
    const std::vector<std::pair<std::string, std::function<void(ResourceFixture&)>>> proof_cases = {
            {"trusted verifier/purpose",
             [](auto& f) { f.proof["source"] = f.resources.at("mapper"); }},
            {"trusted verifier/purpose", [](auto& f) { f.proof["purpose"] = "hermetic-control"; }},
            {"request map",
             [](auto& f) { f.proof["resources"]["mmi"] = f.resources.at("reference"); }},
            {"current resource relationship",
             [](auto& f) { f.resources["reference_fai"] = f.resources.at("reference"); }},
            {"legacy resource relationship",
             [](auto& f) { f.proof["legacy"]["registered_tool"] = f.resources.at("samtools"); }},
            {"verification flags",
             [](auto& f) { f.proof["checks"]["stream_digest_verified"] = false; }},
            {"verification flags", [](auto& f) { f.proof["new_index_built"] = true; }},
            {"verification flags", [](auto& f) { f.proof["new_fai_built"] = true; }},
            {"historical gaps", [](auto& f) { f.proof["historical_index_terminal"] = true; }},
            {"historical gaps",
             [](auto& f) {
                 f.proof["legacy"]["historical_index_controller_source_pin"] = f.trust.verifier;
             }},
            {"missing historical paths",
             [](auto& f) { f.proof["legacy"]["missing_now"] = Json::array(); }},
            {"full contig map",
             [](auto& f) { f.proof["legacy"]["contig_names_lengths"] = {{"foreign", 4}}; }},
            {"stream equivalence", [](auto& f) { f.proof["stream"]["bytes"] = 1; }},
            {"stream equivalence",
             [](auto& f) { f.proof["stream"]["sha256"] = std::string(64, 'f'); }},
            {"stream equivalence", [](auto& f) { f.proof["stream"]["exits"]["gzip"] = 1; }}};
    for (const auto& [message, mutate] : proof_cases) {
        ResourceFixture fixture;
        mutate(fixture);
        fixture.seal();
        rejection([&] { fixture.validate(); }, "resource evidence " + message);
    }
    std::cout << "PASS resource-proof-resealed-resource-and-stream-negatives\n";
    const std::vector<std::pair<std::string, std::function<void(ResourceFixture&)>>> command_cases =
            {{"admitted role/argv", [](auto& f) { f.admission["roles"]["unit"] = "foreign"; }},
             {"admitted role/argv",
              [](auto& f) { f.admission["argv"][9] = f.resources.at("reference").at("path"); }},
             {"admitted source membership",
              [](auto& f) {
                  f.admission["source_pins"].erase(f.admission["source_pins"].begin());
              }},
             {"imported source not admitted",
              [](auto& f) {
                  f.admission["source_pins"].erase(f.admission["source_pins"].begin() + 3);
              }},
             {"semantic input role",
              [](auto& f) {
                  std::swap(f.admission["roles"]["inputs"]["resource-mmi"],
                            f.admission["roles"]["inputs"]["resource-reference"]);
              }},
             {"worker command tuple", [](auto& f) { f.foreign_worker_command = true; }},
             {"worker completion", [](auto& f) { f.worker_terminal["exit"] = 1; }},
             {"outer request binding", [](auto& f) { f.suffix_hash = std::string(64, 'f'); }}};
    for (const auto& [message, mutate] : command_cases) {
        ResourceFixture fixture;
        mutate(fixture);
        fixture.seal();
        rejection([&] { fixture.validate(); }, "resource evidence " + message);
    }
    for (const auto& name : {"publisher", "registered"}) {
        ResourceFixture fixture;
        const auto correct = "resource-" + std::string(name) + "-fai";
        const auto wrong = "resource-" + std::string(name) + "_fai";
        auto& roles = fixture.admission["roles"]["inputs"];
        roles[wrong] = roles.at(correct);
        roles.erase(correct);
        fixture.seal();
        rejection([&] { fixture.validate(); }, correct);
    }
    std::cout << "PASS resource-proof-resealed-admission-source-request-negatives\n";
    for (const auto& key : {"worker_complete", "empty_before_unlock"}) {
        ResourceFixture fixture;
        fixture.outer[key] = false;
        fixture.seal();
        rejection([&] { fixture.validate(); }, "resource evidence outer completion differs");
    }
    ResourceFixture missing;
    missing.seal();
    missing.evidence.erase("outer_terminal");
    missing.json(missing.root / "missing-outer-evidence.json", missing.evidence);
    rejection([&] { missing.validate(); }, "resource evidence tag/trusted spec differs");
    ResourceFixture foreign_outer;
    foreign_outer.seal();
    foreign_outer.evidence["outer_terminal"] = foreign_outer.evidence.at("outer_command");
    foreign_outer.json(foreign_outer.root / "foreign-outer-evidence.json", foreign_outer.evidence);
    rejection([&] { foreign_outer.validate(); }, "resource evidence outer completion differs");
    ResourceFixture stale;
    stale.admission["expires_utc"] = "2026-10-26T23:00:00.000000+00:00";
    stale.seal();
    rejection([&] { stale.validate(); }, "resource evidence admission/worker clocks differ");
    ResourceFixture changed;
    changed.seal();
    std::ofstream append(changed.resources.at("mapper").at("path").get<std::string>(),
                         std::ios::app);
    append << "changed fixture bytes\n";
    append.close();
    rejection([&] { changed.validate(); }, "consumed input pin differs");
    std::cout << Json{{"resource_fixture_root", positive.root.string()},
                      {"retained", true},
                      {"resource_controls", 5},
                      {"synthetic_only", true},
                      {"native_producer_executions", 0}}
                         .dump()
              << '\n';
    std::cout << "PASS resource-proof-outer-custody-current-body-negatives\n";
    return 5;
}
}
